import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Project, Role } from "../api/types";
import { ProjectContextProvider } from "../components/ProjectContext";
import { can, DEFAULT_PERMISSIONS, deniedReason } from "../lib/roles";
import { ShareResultsCard } from "../pages/ProjectPage";

function renderCard(role: Role, reload = vi.fn()) {
  const project: Project = { id: 3, name: "P", slug: "p", description: "", share_results: false, created_by: 1, created_at: "", role };
  render(
    <ProjectContextProvider value={{ project, permissions: DEFAULT_PERMISSIONS, can: (a) => can(role, a), reason: (a) => deniedReason(a), reload }}>
      <ShareResultsCard />
    </ProjectContextProvider>,
  );
  return reload;
}

describe("partage des résultats avec l'IA", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("le propriétaire active le partage", async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response(JSON.stringify({}), { status: 200 })));
    vi.stubGlobal("fetch", fetchMock);
    const reload = renderCard("owner");
    const box = screen.getByRole("checkbox", { name: "Partager les résultats de ce projet avec l'IA" });
    expect(box).not.toBeChecked();
    await userEvent.click(box);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/projects/3");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(String(init.body))).toEqual({ share_results: true });
    expect(reload).toHaveBeenCalled();
  });

  it("un éditeur ne peut pas changer le partage", () => {
    renderCard("editor");
    expect(screen.getByRole("checkbox")).toBeDisabled();
    expect(screen.getByText(deniedReason("edit_project"))).toBeInTheDocument();
  });
});
