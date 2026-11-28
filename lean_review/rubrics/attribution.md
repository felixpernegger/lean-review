# Attribution

Does the PR credit the mathematical sources it follows? Uses `request_changes`, and may `block`
when required credit is clearly absent.

- Credit sources proactively: the paper, textbook, blueprint, notes, or Zulip discussion the work
  follows.
- Check the diff against its stated sources, and watch for laundering: similarity in theorem
  order, notation, or proof plan to an identifiable source is enough to require credit, even
  with no text copied.
- Do not invent attribution requirements for routine work that draws on nothing in
  particular.

## Verdict

- `block` when the PR closely follows an identifiable paper, book or notes with no credit.
- `request_changes` when a central, non-obvious source is named in the description but not the
  code, or is clearly followed but unnamed.
- `approve` when the work credits its central sources.
