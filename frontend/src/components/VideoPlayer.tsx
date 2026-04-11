import { useTimelineStore } from "../stores/timelineStore";
import { PlayerOnly } from "./PlayerOnly";

export function VideoPlayer() {
  const timelineItems = useTimelineStore((s) => s.timelineItems);
  const setPlayerRef = useTimelineStore((s) => s.setPlayerRef);

  if (timelineItems.length === 0) {
    return (
      <div className="video-player empty">
        <div className="video-placeholder">No clips to play</div>
      </div>
    );
  }

  return (
    <div className="video-player">
      <div className="video-player-wrapper">
        <PlayerOnly items={timelineItems} setPlayerRef={setPlayerRef} />
      </div>
    </div>
  );
}
