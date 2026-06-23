export async function first<T>(
  statement: D1PreparedStatement
): Promise<T | null> {
  const result = await statement.first<T>();
  return result ?? null;
}

export async function run(statement: D1PreparedStatement): Promise<void> {
  await statement.run();
}
