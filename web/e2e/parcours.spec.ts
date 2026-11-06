// Parcours complet : inscription, projet, diagnostic jusqu'au résultat,
// invitation d'un lecteur qui voit le run mais ne peut pas en lancer.
// Si SCREENSHOT_DIR est défini, des captures des écrans y sont enregistrées.
import { expect, test, type Page } from "@playwright/test";

const PASSWORD = "motdepasse-solide";
const stamp = Date.now();
const owner = { name: "Ada", email: `ada-${stamp}@example.test` };
const viewer = { name: "Bob", email: `bob-${stamp}@example.test` };

async function shot(page: Page, name: string) {
  const dir = process.env.SCREENSHOT_DIR;
  if (dir) await page.screenshot({ path: `${dir}/${name}.png`, fullPage: true });
}

async function register(page: Page, person: { name: string; email: string }) {
  await page.getByLabel("Nom").fill(person.name);
  await page.getByLabel("Adresse e-mail").fill(person.email);
  await page.getByLabel(/^Mot de passe/).fill(PASSWORD);
  await page.getByLabel("Confirmation du mot de passe").fill(PASSWORD);
  await page.getByRole("button", { name: "Créer le compte" }).click();
}

async function setNumber(page: Page, label: RegExp, value: number) {
  const field = page.getByLabel(label);
  await field.fill(String(value));
}

test("inscription, diagnostic, invitation d'un lecteur", async ({ page }) => {
  // 1. Inscription du propriétaire et création d'un projet.
  await page.goto("/register");
  await shot(page, "01-inscription");
  await register(page, owner);
  await expect(page.getByRole("heading", { name: "Projets", exact: true })).toBeVisible();
  await page.getByLabel("Nom").fill("Projet de bout en bout");
  await page.getByLabel("Description").fill("Parcours Playwright");
  await page.getByRole("button", { name: "Créer le projet" }).click();
  await expect(page.getByRole("heading", { name: "Projet de bout en bout" })).toBeVisible();

  // 2. Diagnostic de petite taille, suivi jusqu'au résultat.
  await page.getByRole("link", { name: "Diagnostic", exact: true }).click();
  await expect(page.getByRole("option", { name: "HardwareEfficient" })).toBeAttached();
  await setNumber(page, /^Qubits/, 2);
  await setNumber(page, /^Couches/, 1);
  await setNumber(page, /^Échantillons/, 50);
  await page.getByRole("button", { name: "Diagnostiquer" }).click();
  await expect(page.getByRole("heading", { name: "Histogramme des fidélités" })).toBeVisible({ timeout: 120_000 });
  await expect(page.getByText("Expressibilité", { exact: true })).toBeVisible();
  await expect(page.getByText("Intrication", { exact: true })).toBeVisible();
  await expect(page.getByText(/Inactifs : \d+ sur \d+/)).toBeVisible();
  await expect(page.locator(".recharts-bar-rectangle").first()).toBeVisible();
  await shot(page, "02-diagnostic");

  // Écrans sans calcul, pour la vérification visuelle.
  await page.getByRole("link", { name: "Ansatz", exact: true }).click();
  await expect(page.getByRole("img", { name: /HardwareEfficient : 4 qubits, 3 couches/ })).toBeVisible();
  await shot(page, "03-ansatz");
  await page.getByRole("link", { name: "Plateau stérile" }).click();
  await page.getByLabel("Mode de couches").selectOption("linear");
  await expect(page.getByText("En mode proportionnel, le nombre de couches est égal au nombre de qubits.")).toBeVisible();
  await shot(page, "04-plateau-sterile-formulaire");

  // 3. Invitation d'un lecteur par lien (aucun e-mail envoyé).
  await page.getByRole("link", { name: "Équipe", exact: true }).click();
  const inviteForm = page.locator("form").filter({ has: page.getByRole("button", { name: "Créer le lien d'invitation" }) });
  await inviteForm.getByLabel("Adresse e-mail").fill(viewer.email);
  await inviteForm.getByLabel(/^Rôle/).selectOption("viewer");
  await inviteForm.getByRole("button", { name: "Créer le lien d'invitation" }).click();
  const link = await page.getByLabel("Lien d'invitation (valable 7 jours)").inputValue();
  expect(link).toContain("/invitations/");
  await shot(page, "05-equipe");
  await page.getByRole("button", { name: "Se déconnecter" }).click();

  // 4. Le lecteur crée son compte depuis le lien, accepte, voit le run.
  await page.goto(new URL(link).pathname);
  await expect(page.getByText("Projet de bout en bout")).toBeVisible();
  await page.getByRole("link", { name: "Créer un compte" }).click();
  await register(page, viewer);
  await page.getByRole("button", { name: "Accepter l'invitation" }).click();
  await expect(page.getByRole("heading", { name: "Projet de bout en bout" })).toBeVisible();
  await expect(page.getByText("Votre rôle : Lecteur")).toBeVisible();
  await page.getByRole("tab", { name: "Runs" }).click();
  await expect(page.getByRole("cell", { name: "Diagnostic" })).toBeVisible();
  await expect(page.getByText("Terminé")).toBeVisible();

  // 5. Il ne peut pas lancer de run : bouton désactivé, avec la raison.
  await page.getByRole("link", { name: "Diagnostic", exact: true }).click();
  const launch = page.getByRole("button", { name: "Diagnostiquer" });
  await expect(launch).toBeDisabled();
  await expect(launch).toHaveAccessibleDescription("Réservé au rôle « Éditeur » ou supérieur.");
  await shot(page, "06-diagnostic-lecteur");

  // Rendu à 390 px de large.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("link", { name: "Équipe", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Équipe", exact: true })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  await shot(page, "07-equipe-390px");
});
