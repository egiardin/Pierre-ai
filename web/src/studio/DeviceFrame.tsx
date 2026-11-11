import { useLayoutEffect, useRef, useState, type ReactNode } from "react";

import type { StudioDevice, StudioMode } from "./studio-context";
import IPhoneFrame from "./IPhoneFrame";
import MacBookFrame from "./MacBookFrame";

interface DeviceFrameProps {
  device: StudioDevice;
  mode: StudioMode;
  /** Adresse affichée dans la barre du navigateur simulé. */
  host: string;
  children: ReactNode;
}

interface Size {
  width: number;
  height: number;
}

interface FrameLayout extends Size {
  scale: number;
}

const REFERENCES: Record<StudioDevice, Size> = {
  mobile: { width: 360, height: 780 },
  desktop: { width: 1260, height: 900 },
};
const SAFE_MARGIN = 32;

function fitFrame(available: Size, reference: Size): FrameLayout {
  const width = Math.max(0, available.width - SAFE_MARGIN * 2);
  const height = Math.max(0, available.height - SAFE_MARGIN * 2);
  const scale = Math.min(width / reference.width, height / reference.height, 1);
  return {
    width: reference.width * scale,
    height: reference.height * scale,
    scale,
  };
}

/**
 * Mesure l'espace restant après la barre du studio et applique un facteur
 * uniforme au châssis. Les dimensions logiques du site ne sont pas réduites.
 */
export default function DeviceFrame({
  device,
  host,
  mode,
  children,
}: DeviceFrameProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const [layout, setLayout] = useState<FrameLayout | null>(null);
  const reference = REFERENCES[device];

  useLayoutEffect(() => {
    const stage = stageRef.current;
    if (!stage) {
      return;
    }

    const update = (size: Size) => {
      const next = fitFrame(size, reference);
      setLayout((current) => {
        if (
          current &&
          Math.abs(current.width - next.width) < 0.25 &&
          Math.abs(current.height - next.height) < 0.25
        ) {
          return current;
        }
        return next;
      });
    };

    update({ width: stage.clientWidth, height: stage.clientHeight });
    if (typeof ResizeObserver === "undefined") {
      const onResize = () =>
        update({ width: stage.clientWidth, height: stage.clientHeight });
      window.addEventListener("resize", onResize);
      return () => window.removeEventListener("resize", onResize);
    }

    const observer = new ResizeObserver(([entry]) => {
      update({
        width: entry.contentRect.width,
        height: entry.contentRect.height,
      });
    });
    observer.observe(stage);
    return () => observer.disconnect();
  }, [reference]);

  const current = layout ?? { width: 0, height: 0, scale: 0 };

  return (
    <div
      ref={stageRef}
      className="device-stage"
      data-device={device}
      data-mode={mode}
      data-reference-width={reference.width}
      data-reference-height={reference.height}
    >
      {current.scale > 0 && (
        <div
          className="device-scale-box"
          data-scale={current.scale.toFixed(4)}
          style={{ width: current.width, height: current.height }}
        >
          <div
            className="device-physical"
            style={{
              width: reference.width,
              height: reference.height,
              transform: `scale(${current.scale})`,
            }}
          >
            {device === "mobile" ? (
              <IPhoneFrame host={host} mode={mode}>
                {children}
              </IPhoneFrame>
            ) : (
              <MacBookFrame host={host} mode={mode}>
                {children}
              </MacBookFrame>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
