const LABEL_CLASS =
  "block font-mono text-xs uppercase tracking-wider font-medium text-secondary mb-2";
const INPUT_CLASS =
  "w-full bg-white text-secondary font-body text-sm border-2 border-secondary rounded-none px-3 py-3 focus:outline-none focus:ring-2 focus:ring-secondary focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed";

function Field({ id, label, required, children }) {
  return (
    <div>
      <label htmlFor={id} className={LABEL_CLASS}>
        {label}
        {required ? " *" : ""}
      </label>
      {children}
    </div>
  );
}

export default function ClaimForm({ fields, values, onChange, disabled }) {
  const today = new Date().toISOString().slice(0, 10);

  function setTopLevel(name, value) {
    onChange({ ...values, [name]: value });
  }

  function setDetail(name, value) {
    onChange({
      ...values,
      details: { ...values.details, [name]: value },
    });
  }

  return (
    <div className="space-y-6">
      <Field id="loss_date" label="Date of loss" required>
        <input
          id="loss_date"
          type="date"
          max={today}
          value={values.loss_date}
          disabled={disabled}
          onChange={(e) => setTopLevel("loss_date", e.target.value)}
          className={INPUT_CLASS}
        />
      </Field>

      <Field id="claimed_amount" label="Claimed amount" required>
        <input
          id="claimed_amount"
          type="number"
          min="0"
          step="0.01"
          value={values.claimed_amount}
          disabled={disabled}
          onChange={(e) => setTopLevel("claimed_amount", e.target.value)}
          className={INPUT_CLASS}
        />
      </Field>

      {fields.map((field) => (
        <Field
          key={field.name}
          id={`detail-${field.name}`}
          label={field.label}
          required={field.required}
        >
          {field.type === "select" ? (
            <select
              id={`detail-${field.name}`}
              value={values.details[field.name] || ""}
              disabled={disabled}
              onChange={(e) => setDetail(field.name, e.target.value)}
              className={INPUT_CLASS}
            >
              <option value="">Select...</option>
              {field.options.map((option) => (
                <option key={option} value={option}>
                  {option.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          ) : (
            <input
              id={`detail-${field.name}`}
              type={field.type}
              value={values.details[field.name] || ""}
              disabled={disabled}
              onChange={(e) => setDetail(field.name, e.target.value)}
              className={INPUT_CLASS}
            />
          )}
        </Field>
      ))}

      <Field id="description" label="What happened?">
        <textarea
          id="description"
          rows={4}
          maxLength={2000}
          value={values.description}
          disabled={disabled}
          onChange={(e) => setTopLevel("description", e.target.value)}
          className={INPUT_CLASS}
        />
      </Field>
    </div>
  );
}