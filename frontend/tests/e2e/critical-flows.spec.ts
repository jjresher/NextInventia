import { expect, test } from "@playwright/test";

test("muestra el catálogo servido por la API falsa", async ({ page }) => {
  const response = await page.goto("/");

  await expect(page.getByRole("heading", { name: "Buscador de Patentes" })).toBeVisible();
  await expect(page.getByText("Patente de prueba")).toBeVisible();
  expect(response?.headers()["content-security-policy-report-only"]).toContain(
    "frame-ancestors 'none'"
  );
  expect(response?.headers()["x-frame-options"]).toBe("DENY");
  expect(response?.headers()["strict-transport-security"]).toContain("max-age=31536000");
});

test("abre una patente y conversa sin servicios reales", async ({ page }) => {
  await page.goto("/patentes/1");
  await expect(page.getByRole("heading", { name: "Patente de prueba" })).toBeVisible();

  await page.getByRole("button", { name: "PatentBot" }).click();
  await page.getByPlaceholder("Pregunta sobre estas patentes...").fill("¿De qué trata?");
  await page.getByPlaceholder("Pregunta sobre estas patentes...").press("Enter");

  await expect(page.getByText("Respuesta del chat falso.")).toBeVisible();
});

test("distingue patente inexistente de fallo recuperable", async ({ page }) => {
  await page.goto("/patentes/404");
  await expect(page.getByRole("heading", { name: "404" })).toBeVisible();

  await page.goto("/patentes/500");
  await expect(
    page.getByRole("heading", { name: "No pudimos cargar esta patente" })
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Reintentar" })).toBeVisible();
});

test("convierte una respuesta incompatible en un error controlado", async ({ page }) => {
  await page.goto("/patentes/2");

  await expect(
    page.getByRole("heading", { name: "No pudimos cargar esta patente" })
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Reintentar" })).toBeVisible();
});

test("clasifica una descripción mediante la API falsa", async ({ page }) => {
  await page.goto("/clasificar");
  await page.getByPlaceholder(/sistema electrónico/).fill(
    "Sistema electrónico para controlar la inyección de combustible del motor."
  );
  await page.getByRole("button", { name: "Analizar clasificación CPC" }).click();

  await expect(page.getByText("F02D 41/00")).toBeVisible();
});
