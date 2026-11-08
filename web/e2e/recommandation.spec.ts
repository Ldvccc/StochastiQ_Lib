// Parcours v0.3 : problème de référence, ansatz personnalisé, entraînement,
// recommandation, rapport imprimable, puis vérification à 390 px de large.
// La configuration (playwright.config.ts) entraîne un modèle de prédiction réduit dans un
// MODELS_DIR temporaire avant de démarrer l'API.
import { expect, test, type Page } from "@playwright/test";

const PASSWORD = "motdepasse-solide";
const owner = { name: "Chloé", email: `chloe-${Date.now()}@example.test` };

async function shot(page: Page, name: string) {
  const dir = process.env.SCREENSHOT_DIR;
  if (dir) await page.screenshot({ path: `${dir}/${name}.png`, fullPage: true });
}

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

test("problème, ansatz personnalisé, entraînement, recommandation et rapport", async ({ page }) => {
  // 1. Compte et projet.
  await page.goto("/register");
  await page.getByLabel("Nom").fill(owner.name);
  await page.getByLabel("Adresse e-mail").fill(owner.email);
  await page.getByLabel(/^Mot de passe/).fill(PASSWORD);
  await page.getByLabel("Confirmation du mot de passe").fill(PASSWORD);
  await page.getByRole("button", { name: "Créer le compte" }).click();
  await expect(page.getByRole("heading", { name: "Projets", exact: true })).toBeVisible();
  await page.getByLabel("Nom").fill("Projet recommandation");
  await page.getByRole("button", { name: "Créer le projet" }).click();
  await expect(page.getByRole("heading", { name: "Projet recommandation" })).toBeVisible();

  // 2. Problème depuis une distribution de référence (gaussienne, 3 qubits).
  await page.getByRole("link", { name: "Problèmes", exact: true }).click();
  const reference = page.getByRole("form", { name: "Problème depuis une référence" });
  await expect(reference.getByRole("option", { name: /aussi/ }).first()).toBeAttached();
  await reference.getByLabel("Nom", { exact: true }).fill("Gauss 3");
  await reference.getByLabel("Distribution").selectOption("gaussian");
  await reference.getByLabel(/^Qubits/).fill("3");
  await reference.getByRole("button", { name: "Créer le problème" }).click();
  await expect(page.getByRole("cell", { name: "Gauss 3" })).toBeVisible();

  // 3. Ansatz personnalisé par spec (valeurs par défaut du formulaire).
  await page.getByRole("link", { name: "Mes ansatz", exact: true }).click();
  const spec = page.getByRole("form", { name: "Ansatz par spec" });
  await spec.getByLabel("Nom", { exact: true }).fill("Mon ansatz");
  await spec.getByRole("button", { name: "Enregistrer l'ansatz" }).click();
  await expect(page.getByRole("img", { name: /Mon ansatz/ })).toBeVisible();

  // 4. Entraînement court de l'ansatz personnalisé.
  await page.getByRole("link", { name: "Entraînement", exact: true }).click();
  const training = page.getByRole("form", { name: "Paramètres de l'entraînement" });
  await training.getByRole("combobox", { name: /^Problème/ }).selectOption({ label: "Gauss 3 (3 qubits)" });
  await training.getByRole("combobox", { name: /^Ansatz/ }).selectOption({ label: "Mon ansatz (personnalisé)" });
  await training.getByLabel(/^Couches/).fill("1");
  await training.getByLabel(/^Itérations/).fill("20");
  await training.getByRole("button", { name: "Lancer l'entraînement" }).click();
  await expect(page.getByRole("heading", { name: "Quantique contre classique" })).toBeVisible({ timeout: 120_000 });

  // 5. Recommandation : deux ansatz du catalogue et l'ansatz personnalisé, déjà entraîné.
  await page.getByRole("link", { name: "Recommandation", exact: true }).click();
  const form = page.getByRole("form", { name: "Paramètres de la recommandation" });
  await form.getByRole("combobox", { name: /^Problème/ }).selectOption({ label: "Gauss 3 (3 qubits)" });
  await form.getByLabel(/^Couches/).fill("1");
  await form.getByRole("checkbox", { name: "Mon ansatz (personnalisé)" }).check();
  await form.getByRole("button", { name: "Recommander" }).click();
  await expect(page.getByRole("heading", { name: "Verdict" })).toBeVisible({ timeout: 180_000 });
  await expect(page.getByText(/Le quantique se justifie|Le quantique ne se justifie pas|Indéterminé/).first()).toBeVisible();
  await expect(page.getByText(/Entraînement mesuré \(run n° \d+\)/)).toBeVisible();
  await expect(page.getByText("Référence classique : arbre de Chow-Liu")).toBeVisible();
  await shot(page, "10-recommandation");

  // 6. Rapport imprimable : navigation masquée à l'impression.
  await page.getByRole("link", { name: "Ouvrir le rapport imprimable" }).click();
  await expect(page.getByRole("heading", { name: "Rapport de recommandation" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Exporter en JSON" })).toBeVisible();
  await page.emulateMedia({ media: "print" });
  await expect(page.getByRole("navigation", { name: "Navigation principale" })).toBeHidden();
  await expect(page.getByRole("button", { name: "Imprimer" })).toBeHidden();
  await shot(page, "11-rapport-impression");
  await page.emulateMedia({ media: "screen" });

  // 7. Largeur de téléphone : aucun défilement horizontal de la page.
  await page.setViewportSize({ width: 390, height: 844 });
  await noHorizontalScroll(page);
  await shot(page, "12-rapport-390");
  await page.getByRole("link", { name: "Retour à la recommandation" }).click();
  await expect(page.getByRole("heading", { name: "Verdict" })).toBeVisible();
  await noHorizontalScroll(page);
  await shot(page, "13-recommandation-390");
});
