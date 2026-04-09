import { AbsoluteFill, Series, OffthreadVideo } from "remotion";
import { secondsToFrames } from "../lib/remotion";
import type { TimelineItem } from "../types";

const PREMOUNT_FRAMES = 30; // 1s at 30fps

interface Props {
  items: TimelineItem[];
}

export const TimelineComposition: React.FC<Props> = ({ items }) => {
  const filtered = items.filter((item) => item.duration >= 0.034);

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Series>
        {filtered.map((item) => {
          const durationInFrames = Math.max(secondsToFrames(item.duration), 1);
          const videoStartFrame = secondsToFrames(item.start_time);

          return (
            <Series.Sequence
              key={`${item.id}-${item.position}`}
              durationInFrames={durationInFrames}
              premountFor={PREMOUNT_FRAMES}
            >
              <AbsoluteFill>
                <OffthreadVideo
                  src={item.video_url}
                  startFrom={videoStartFrame}
                  endAt={videoStartFrame + durationInFrames}
                  pauseWhenBuffering
                  style={{ width: "100%", height: "100%", objectFit: "contain" }}
                />
              </AbsoluteFill>
            </Series.Sequence>
          );
        })}
      </Series>
    </AbsoluteFill>
  );
};
