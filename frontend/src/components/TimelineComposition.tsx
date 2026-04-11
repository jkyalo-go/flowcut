import React, { useMemo } from "react";
import { AbsoluteFill, OffthreadVideo, Sequence, useCurrentFrame } from "remotion";
import { secondsToFrames } from "../lib/remotion";
import type { TimelineItem } from "../types";

const PREMOUNT_FRAMES = 30;

interface Props {
  items: TimelineItem[];
}

interface ClipLayout {
  item: TimelineItem;
  startFrame: number;
  durationInFrames: number;
}

export const TimelineComposition: React.FC<Props> = React.memo(({ items }) => {
  const frame = useCurrentFrame();

  const layout = useMemo(() => {
    let cursor = 0;
    const result: ClipLayout[] = [];
    for (const item of items) {
      if (item.duration < 0.034) continue;
      const dur = Math.max(secondsToFrames(item.duration), 1);
      result.push({ item, startFrame: cursor, durationInFrames: dur });
      cursor += dur;
    }
    return result;
  }, [items]);

  let activeIdx = -1;
  for (let i = 0; i < layout.length; i++) {
    const clip = layout[i];
    if (frame >= clip.startFrame && frame < clip.startFrame + clip.durationInFrames) {
      activeIdx = i;
      break;
    }
  }
  if (activeIdx === -1 && layout.length > 0) {
    activeIdx = layout.length - 1;
  }

  const toMount = [activeIdx - 1, activeIdx, activeIdx + 1].filter(
    (i) => i >= 0 && i < layout.length
  );

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {toMount.map((i) => {
        const clip = layout[i];
        const videoStartFrame = secondsToFrames(clip.item.start_time);

        return (
          <Sequence
            key={`${clip.item.id}-${clip.item.position}`}
            from={clip.startFrame}
            durationInFrames={clip.durationInFrames}
            premountFor={PREMOUNT_FRAMES}
          >
            <AbsoluteFill>
              <OffthreadVideo
                src={clip.item.video_url}
                startFrom={videoStartFrame}
                endAt={videoStartFrame + clip.durationInFrames}
                pauseWhenBuffering
                style={{ width: "100%", height: "100%", objectFit: "contain" }}
              />
            </AbsoluteFill>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
});
