export function getUserId(): string {
  const existing = localStorage.getItem("userId");
  if (existing) return existing;

  const created = crypto.randomUUID();
  localStorage.setItem("userId", created);
  return created;
}
