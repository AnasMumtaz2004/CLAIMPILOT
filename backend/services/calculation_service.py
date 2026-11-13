from decimal import Decimal
from decimal import ROUND_HALF_UP

# Money is kept to two decimal places (paise)
TWO_PLACES = Decimal("0.01")

# Under this ratio the average clause applies (guidelines section 5.1 and 8.1)
UNDERINSURANCE_WAIVER_RATIO = Decimal("0.85")


def to_money(value, name):
    """Convert a number to a Decimal and reject negative values."""
    try:
        amount = Decimal(str(value))
    except Exception:
        raise ValueError(f"{name} must be a number.")

    if amount < 0:
        raise ValueError(f"{name} cannot be negative.")
    return amount


def round_money(amount):
    """Round an amount to two decimal places, half up."""
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def to_float(amount):
    """Convert a Decimal to a float that is safe to save as JSON."""
    return float(round_money(amount))


def calculate_remaining_sum_insured(sum_insured, already_paid):
    """Return the sum insured that is still left after earlier payouts."""
    total = to_money(sum_insured, "Sum insured")
    paid = to_money(already_paid, "Already paid amount")
    return to_float(max(total - paid, Decimal("0")))


def read_line_item(item, number):
    """Check one bill line item and return it with Decimal amounts."""
    name = str(item.get("name", f"Item {number}"))
    amount = to_money(item.get("amount", 0), f"Amount of '{name}'")
    admissible = bool(item.get("admissible", True))

    sub_limit = item.get("sub_limit")
    if sub_limit is not None:
        sub_limit = to_money(sub_limit, f"Sub-limit of '{name}'")

    depreciation_percent = to_money(item.get("depreciation_percent", 0), f"Depreciation of '{name}'")
    if depreciation_percent > 100:
        raise ValueError(f"Depreciation of '{name}' cannot be more than 100%.")

    return {
        "name": name,
        "amount": amount,
        "admissible": admissible,
        "sub_limit": sub_limit,
        "depreciation_percent": depreciation_percent,
    }


def make_step(number, name, label, removed, balance, note):
    """Build one row of the calculation breakdown."""
    return {
        "step": number,
        "name": name,
        "label": label,
        "amount_removed": to_float(removed),
        "balance": to_float(balance),
        "note": note,
    }


def calculate_claim_amount(
    line_items,
    salvage_value=0,
    sum_insured=None,
    value_at_risk=None,
    copay_percent=0,
    deductible=0,
    remaining_sum_insured=None,
):
    """Work out the payable amount using the nine steps in the internal guidelines, section 8.1."""
    items = []
    for number, item in enumerate(line_items, start=1):
        items.append(read_line_item(item, number))

    salvage = to_money(salvage_value, "Salvage value")
    copay = to_money(copay_percent, "Co-payment percent")
    if copay > 100:
        raise ValueError("Co-payment percent cannot be more than 100.")
    fixed_deductible = to_money(deductible, "Deductible")

    steps = []

    # Step 1: add up every submitted line item
    gross = Decimal("0")
    for item in items:
        gross = gross + item["amount"]
    balance = gross
    steps.append(make_step(1, "gross_claim_amount", "Gross claim amount", Decimal("0"), balance, "Sum of all submitted line items."))

    # Step 2: remove items the policy does not cover
    non_admissible = Decimal("0")
    for item in items:
        if not item["admissible"]:
            non_admissible = non_admissible + item["amount"]
    balance = balance - non_admissible
    steps.append(make_step(2, "non_admissible_items", "Less non-admissible items", non_admissible, balance, "Items marked as not covered."))

    # Step 3: cap each admissible item at its own sub-limit
    sub_limit_cut = Decimal("0")
    for item in items:
        item["after_sub_limit"] = item["amount"]
        if not item["admissible"]:
            item["after_sub_limit"] = Decimal("0")
            continue
        if item["sub_limit"] is not None and item["amount"] > item["sub_limit"]:
            sub_limit_cut = sub_limit_cut + (item["amount"] - item["sub_limit"])
            item["after_sub_limit"] = item["sub_limit"]
    balance = balance - sub_limit_cut
    steps.append(make_step(3, "sub_limit_caps", "Less sub-limit caps", sub_limit_cut, balance, "Each item is capped at its own sub-limit."))

    # Step 4: remove depreciation from each item
    depreciation_total = Decimal("0")
    for item in items:
        depreciation = round_money(item["after_sub_limit"] * item["depreciation_percent"] / Decimal("100"))
        item["depreciation"] = depreciation
        depreciation_total = depreciation_total + depreciation
    balance = balance - depreciation_total
    steps.append(make_step(4, "depreciation", "Less depreciation", depreciation_total, balance, "Depreciation is applied item by item."))

    # Step 5: remove the salvage value, but never more than the balance
    salvage_removed = min(salvage, balance)
    balance = balance - salvage_removed
    note = "Scrap or salvage value."
    if salvage > salvage_removed:
        note = "Salvage was larger than the balance, so only the balance was removed."
    steps.append(make_step(5, "salvage_value", "Less salvage value", salvage_removed, balance, note))

    # Step 6: apply the average clause when the sum insured is too low
    underinsurance_ratio = None
    reduction = Decimal("0")
    note = "Not applicable. Sum insured and value at risk were not both given."
    if sum_insured is not None and value_at_risk is not None:
        insured = to_money(sum_insured, "Sum insured")
        at_risk = to_money(value_at_risk, "Value at risk")
        if at_risk == 0:
            raise ValueError("Value at risk must be more than zero.")

        underinsurance_ratio = insured / at_risk
        if underinsurance_ratio >= UNDERINSURANCE_WAIVER_RATIO:
            note = "Waived. The sum insured is at least 85% of the value at risk."
        else:
            reduced = round_money(balance * insured / at_risk)
            reduction = balance - reduced
            balance = reduced
            note = "Applied. The sum insured is below 85% of the value at risk."
    steps.append(make_step(6, "underinsurance", "Apply underinsurance (average clause)", reduction, balance, note))

    # Step 7: co-payment is a percentage of the balance
    copay_amount = round_money(balance * copay / Decimal("100"))
    balance = balance - copay_amount
    steps.append(make_step(7, "co_payment", "Less co-payment", copay_amount, balance, "Percentage of the balance."))

    # Step 8: the deductible is a fixed amount, never more than the balance
    deductible_removed = min(fixed_deductible, balance)
    balance = balance - deductible_removed
    steps.append(make_step(8, "deductible", "Less deductible", deductible_removed, balance, "Fixed amount per claim."))

    # Step 9: the payout can never be more than the remaining sum insured
    capped = False
    cap_removed = Decimal("0")
    note = "No remaining sum insured was given, so no cap was applied."
    if remaining_sum_insured is not None:
        remaining = to_money(remaining_sum_insured, "Remaining sum insured")
        note = "The balance is within the remaining sum insured."
        if balance > remaining:
            cap_removed = balance - remaining
            balance = remaining
            capped = True
            note = "The balance was cut to the remaining sum insured."
    steps.append(make_step(9, "cap_at_remaining_sum_insured", "Cap at remaining sum insured", cap_removed, balance, note))

    line_results = []
    for item in items:
        line_results.append({
            "name": item["name"],
            "claimed": to_float(item["amount"]),
            "admissible": item["admissible"],
            "after_sub_limit": to_float(item["after_sub_limit"]),
            "depreciation": to_float(item["depreciation"]),
            "after_depreciation": to_float(item["after_sub_limit"] - item["depreciation"]),
        })

    ratio_value = None
    if underinsurance_ratio is not None:
        ratio_value = float(underinsurance_ratio.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))

    return {
        "gross_amount": to_float(gross),
        "final_payable": to_float(balance),
        "total_deductions": to_float(gross - balance),
        "capped_by_remaining_sum_insured": capped,
        "underinsurance_ratio": ratio_value,
        "steps": steps,
        "line_items": line_results,
    }