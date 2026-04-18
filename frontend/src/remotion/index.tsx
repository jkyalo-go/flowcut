import React from "react";
import { registerRoot, Composition } from "remotion";
import { TimelineComposition } from "../components/TimelineComposition";
import { FPS } from "../lib/remotion";

const RemotionRoot: React.FC = () => (
  <Composition
    id="Timeline"
    component={TimelineComposition as unknown as React.ComponentType<Record<string, unknown>>}
    fps={FPS}
    width={1920}
    height={1080}
    durationInFrames={1}
    defaultProps={{ items: [] }}
  />
);

registerRoot(RemotionRoot);
