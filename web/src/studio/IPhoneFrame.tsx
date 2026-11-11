import type { ReactNode } from "react";

import type { StudioMode } from "./studio-context";

interface IPhoneFrameProps {
  host: string;
  mode: StudioMode;
  children: ReactNode;
}

/** Châssis iPhone de taille logique constante ; seul son contenu défile. */
export default function IPhoneFrame({
  host,
  mode,
  children,
}: IPhoneFrameProps) {
  return (
    <div className="device-phone" data-physical-frame="iphone">
      <span className="phone-button phone-button-left" aria-hidden="true" />
      <span className="phone-button phone-button-right" aria-hidden="true" />
      <div className="phone-screen">
        <div className="phone-status">
          <span className="phone-time">9:41</span>
          <span className="phone-island" aria-hidden="true" />
          <svg
            className="phone-icons"
            width="58"
            height="12"
            viewBox="0 0 58 12"
            aria-hidden="true"
            fill="currentColor"
          >
            <rect x="0" y="7" width="3" height="4" rx="1" />
            <rect x="4.6" y="5" width="3" height="6" rx="1" />
            <rect x="9.2" y="3" width="3" height="8" rx="1" />
            <rect x="13.8" y="1" width="3" height="10" rx="1" />
            <path d="M21.6 4.6a8.4 8.4 0 0 1 10.2 0l-2 2.4a5.2 5.2 0 0 0-6.2 0z" />
            <circle cx="26.7" cy="9.2" r="1.7" />
            <rect
              x="37"
              y="2.6"
              width="17"
              height="7"
              rx="2.2"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.3"
            />
            <rect x="38.6" y="4.2" width="11.8" height="3.8" rx="1.2" />
            <rect x="55.2" y="4.8" width="1.6" height="2.8" rx="0.8" />
          </svg>
        </div>
        <div className="device-viewport phone-viewport" key={mode}>
          {children}
        </div>
        <div className="phone-browser-bar">
          <span className="phone-browser-icon" aria-hidden="true">
            ‹
          </span>
          <span className="phone-address">{host}</span>
          <span className="phone-browser-icon" aria-hidden="true">
            •••
          </span>
        </div>
        <div className="phone-toolbar" aria-hidden="true">
          <span>‹</span>
          <span>›</span>
          <span>□</span>
          <span>▤</span>
        </div>
        <div className="phone-home" aria-hidden="true" />
      </div>
    </div>
  );
}
