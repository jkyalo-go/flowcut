import { useRef, useEffect, useMemo } from "react";
import { Player, type PlayerRef } from "@remotion/player";
import { useTimelineStore } from "../stores/timelineStore";
import { TimelineComposition } from "./TimelineComposition";
import { FPS, totalDurationInFrames } from "../lib/remotion";

export function VideoPlayer() {
  const timelineItems = useTimelineStore((s) => s.timelineItems);
  const setPlayerRef = useTimelineStore((s) => s.setPlayerRef);
  const playerRef = useRef<PlayerRef | null>(null);

  const durationInFrames = useMemo(
    () => Math.max(totalDurationInFrames(timelineItems), 1),
    [timelineItems]
  );

  const inputProps = useMemo(
    () => ({ items: timelineItems }),
    [timelineItems]
  );

  useEffect(() => {
    setPlayerRef(playerRef);
    return () => setPlayerRef(null);
  }, [setPlayerRef]);

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
        <Player
          ref={playerRef}
          component={TimelineComposition}
          inputProps={inputProps}
          durationInFrames={durationInFrames}
          fps={FPS}
          compositionWidth={1920}
          compositionHeight={1080}
          style={{ width: "100%", height: "100%" }}
          controls
          autoPlay={false}
          loop={false}
          acknowledgeRemotionLicense
        />
      </div>
    </div>
  );
}
