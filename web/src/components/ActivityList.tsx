import type { ActivityEvent } from "../api/types";
import { describeEvent } from "../lib/activity";
import { formatDateTime } from "../lib/format";
import { Empty } from "./common";

export function ActivityList({ events }: { events: ActivityEvent[] }) {
  if (events.length === 0) return <Empty>Aucune activité pour l'instant.</Empty>;
  return (
    <ul className="activity" aria-label="Fil d'activité">
      {events.map((event) => (
        <li key={event.id}>
          <span>{describeEvent(event)}</span>
          <time className="muted num" dateTime={event.created_at}>
            {formatDateTime(event.created_at)}
          </time>
        </li>
      ))}
    </ul>
  );
}
