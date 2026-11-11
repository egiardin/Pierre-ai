import type { ReactNode } from "react";

import type { StudioMode } from "./studio-context";

interface MacBookFrameProps {
  host: string;
  mode: StudioMode;
  children: ReactNode;
}

/** Représentation frontale d'un MacBook Pro avec Safari dans son écran. */
export default function MacBookFrame({
  host,
  mode,
  children,
}: MacBookFrameProps) {
  return (
    <div className="macbook-frame" data-physical-frame="macbook">
      <div className="macbook-lid">
        <span className="macbook-camera" aria-hidden="true" />
        <div className="macbook-display">
          <div className="macbook-safari">
            <div className="macbook-safari-lights" aria-hidden="true">
              <i />
              <i />
              <i />
            </div>
            <div className="macbook-safari-nav" aria-hidden="true">
              <span>‹</span>
              <span>›</span>
            </div>
            <div className="macbook-address" title={host}>
              <span className="macbook-lock" aria-hidden="true">
                ◈
              </span>
              <span>{host}</span>
              <span className="macbook-reload" aria-hidden="true">
                ↻
              </span>
            </div>
            <div className="macbook-safari-actions" aria-hidden="true">
              <span>⇧</span>
              <span>＋</span>
              <span>▤</span>
            </div>
          </div>
          <div className="device-viewport macbook-viewport" key={mode}>
            {children}
          </div>
        </div>
      </div>
      <div className="macbook-hinge" aria-hidden="true" />
      <div className="macbook-base" aria-hidden="true">
        <div className="macbook-keyboard" />
        <div className="macbook-trackpad" />
        <span className="macbook-front-lip" />
      </div>
    </div>
  );
}
