import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ActivityEvent, Member } from "../api/types";
import { ActivityList } from "../components/ActivityList";
import { GuardedButton } from "../components/common";
import { MembersTable } from "../components/MembersTable";
import { describeEvent } from "../lib/activity";
import { formatFactor, formatFr, formatMetric, formatPercent } from "../lib/format";
import { can, deniedReason, DEFAULT_PERMISSIONS } from "../lib/roles";
import { PermissionMatrix } from "../pages/TeamPage";

const MEMBERS: Member[] = [
  { user_id: 1, email: "ada@example.test", name: "Ada", role: "owner", title: "CEO", created_at: "" },
  { user_id: 2, email: "bob@example.test", name: "Bob", role: "viewer", title: "", created_at: "" },
];

function table(canManage: boolean, onChange = vi.fn(async () => {}), onRemove = vi.fn(async () => {})) {
  render(
    <MembersTable
      members={MEMBERS}
      currentUserId={1}
      canManage={canManage}
      deniedReason={deniedReason("manage_members")}
      onChange={onChange}
      onRemove={onRemove}
    />,
  );
  return { onChange, onRemove };
}

describe("tableau des membres", () => {
  it("affiche les membres avec rôle et titre", () => {
    table(true);
    const rows = screen.getAllByRole("row");
    expect(rows).toHaveLength(3);
    expect(within(rows[1]).getByText("Ada")).toBeInTheDocument();
    expect(within(rows[1]).getByText("(vous)")).toBeInTheDocument();
    expect(screen.getByLabelText("Rôle de Bob")).toHaveValue("viewer");
    expect(screen.getByLabelText("Titre de Ada")).toHaveValue("CEO");
  });

  it("le propriétaire change un rôle", async () => {
    const { onChange } = table(true);
    await userEvent.selectOptions(screen.getByLabelText("Rôle de Bob"), "editor");
    expect(onChange).toHaveBeenCalledWith(2, { role: "editor" });
  });

  it("sans droit, les actions sont désactivées avec une explication, pas masquées", async () => {
    const { onRemove } = table(false);
    const select = screen.getByLabelText("Rôle de Bob");
    expect(select).toBeDisabled();
    expect(select).toHaveAttribute("title", "Réservé au rôle « Propriétaire » ou supérieur.");
    const remove = screen.getAllByRole("button", { name: "Retirer" })[1];
    expect(remove).toBeDisabled();
    expect(remove).toHaveAccessibleDescription("Réservé au rôle « Propriétaire » ou supérieur.");
    await userEvent.click(remove);
    expect(onRemove).not.toHaveBeenCalled();
  });
});

describe("affichage selon le rôle", () => {
  it("matrice de droits", () => {
    expect(can("viewer", "comment")).toBe(true);
    expect(can("viewer", "run")).toBe(false);
    expect(can("editor", "run")).toBe(true);
    expect(can("editor", "machines")).toBe(false);
    expect(can("key_manager", "machines")).toBe(true);
    expect(can("key_manager", "invite")).toBe(false);
    expect(can("owner", "delete_project")).toBe(true);
  });

  it("bouton protégé : actif si autorisé, désactivé avec raison sinon", async () => {
    const onClick = vi.fn();
    const { rerender } = render(
      <GuardedButton allowed reason="Interdit" onClick={onClick}>
        Lancer
      </GuardedButton>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Lancer" }));
    expect(onClick).toHaveBeenCalledTimes(1);
    rerender(
      <GuardedButton allowed={false} reason={deniedReason("run")} onClick={onClick}>
        Lancer
      </GuardedButton>,
    );
    const button = screen.getByRole("button", { name: "Lancer" });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription("Réservé au rôle « Éditeur » ou supérieur.");
  });

  it("tableau « ce que chaque rôle permet »", () => {
    render(<PermissionMatrix permissions={DEFAULT_PERMISSIONS} />);
    const row = screen.getByRole("row", { name: /Lancer des runs/ });
    expect(within(row).getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["Non", "Oui", "Oui", "Oui"]);
  });
});

const EVENTS: ActivityEvent[] = [
  { id: 3, type: "run_done", user: { id: 1, name: "Ada" }, payload: { run_id: 4, kind: "diagnostic" }, created_at: "2026-11-06T10:00:00" },
  { id: 2, type: "role_changed", user: { id: 1, name: "Ada" }, payload: { name: "Bob", old_role: "viewer", new_role: "editor" }, created_at: "2026-11-06T09:00:00" },
  { id: 1, type: "member_invited", user: null, payload: { email: "c@example.test", role: "key_manager" }, created_at: "2026-11-06T08:00:00" },
];

describe("fil d'activité", () => {
  it("décrit chaque événement en français", () => {
    expect(describeEvent(EVENTS[0])).toBe("Le run de diagnostic n° 4 est terminé.");
    expect(describeEvent(EVENTS[1])).toBe("Ada a changé le rôle de Bob : lecteur vers éditeur.");
    expect(describeEvent(EVENTS[2])).toBe("Un ancien membre a invité c@example.test comme gestionnaire des machines.");
  });

  it("carte du fil d'activité", () => {
    render(<ActivityList events={EVENTS} />);
    const items = within(screen.getByRole("list", { name: "Fil d'activité" })).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent("Le run de diagnostic n° 4 est terminé.");
  });

  it("état vide", () => {
    render(<ActivityList events={[]} />);
    expect(screen.getByText("Aucune activité pour l'instant.")).toBeInTheDocument();
  });
});

describe("formatage français", () => {
  it("virgule décimale", () => {
    expect(formatFr(0.14159, 4)).toBe("0,1416");
    expect(formatMetric(0.000012)).toBe("0,0000");
    expect(formatMetric(null)).toBe("n/a");
    expect(formatFactor(3)).toBe("×3,00");
    expect(formatPercent(1 / 3)).toBe("33,3 %");
    expect(formatFr(-0.00001, 2)).toBe("0,00");
  });
});
