import React, { useRef, useEffect, useMemo, type RefObject } from "react";
import { Player, type PlayerRef } from "@remotion/player";
import { TimelineComposition } from "./TimelineComposition";
import { FPS, totalDurationInFrames } from "../lib/remotion";
import type { TimelineItem } from "../types";

interface Props {
  items: TimelineItem[];
  setPlayerRef: (ref: RefObject<PlayerRef | null> | null) => void;
}

export const PlayerOnly = React.memo(function PlayerOnly({ items, setPlayerRef }: Props) {
  const playerRef = useRef<PlayerRef | null>(null);

  const durationInFrames = useMemo(
    () => Math.max(totalDurationInFrames(items), 1),
    [items]
  );

  const inputProps = useMemo(
    () => ({ items }),
    [items]
  );

  useEffect(() => {
    setPlayerRef(playerRef);
    return () => setPlayerRef(null);
  }, [setPlayerRef]);

  return (
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
  );
});
