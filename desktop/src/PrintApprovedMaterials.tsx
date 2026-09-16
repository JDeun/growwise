import { useState } from "react";

import {
  DEFAULT_PRINT_LAYOUT,
  type PaperSize,
  type PrintOrientation,
  printPageRule,
  sanitizePrintLayout,
} from "./print-layout";

const PRINT_SCOPE_ATTRIBUTE = "data-growwise-print-scope";
const PRINT_LAYOUT_SELECTOR = 'style[data-growwise-print-layout="true"]';

function PrintApprovedMaterials() {
  const [layout, setLayout] = useState(DEFAULT_PRINT_LAYOUT);

  function handlePrint() {
    const approved = document.querySelector(".approved-card");
    if (!approved) {
      window.alert("현재 아이에 승인된 자료가 없습니다.");
      return;
    }

    const style = document.createElement("style");
    style.dataset.growwisePrintLayout = "true";
    style.textContent = printPageRule(layout);
    document.head.querySelector(PRINT_LAYOUT_SELECTOR)?.remove();
    document.head.appendChild(style);
    document.body.setAttribute(PRINT_SCOPE_ATTRIBUTE, "approved");

    const cleanup = () => {
      document.body.removeAttribute(PRINT_SCOPE_ATTRIBUTE);
      document.head.querySelector(PRINT_LAYOUT_SELECTOR)?.remove();
      window.removeEventListener("afterprint", cleanup);
    };

    window.addEventListener("afterprint", cleanup, { once: true });
    try {
      window.print();
    } catch (error) {
      cleanup();
      throw error;
    }
  }

  return (
    <aside className="print-toolbar" aria-label="자료 내보내기">
      <label>
        용지
        <select
          aria-label="인쇄 용지"
          value={layout.paperSize}
          onChange={(event) =>
            setLayout((current) =>
              sanitizePrintLayout({ ...current, paperSize: event.target.value as PaperSize }),
            )
          }
        >
          <option value="A4">A4</option>
          <option value="Letter">Letter</option>
        </select>
      </label>
      <label>
        방향
        <select
          aria-label="인쇄 방향"
          value={layout.orientation}
          onChange={(event) =>
            setLayout((current) =>
              sanitizePrintLayout({
                ...current,
                orientation: event.target.value as PrintOrientation,
              }),
            )
          }
        >
          <option value="portrait">세로</option>
          <option value="landscape">가로</option>
        </select>
      </label>
      <label>
        여백(mm)
        <input
          aria-label="인쇄 여백"
          type="number"
          min="5"
          max="40"
          value={layout.marginMm}
          onChange={(event) =>
            setLayout((current) =>
              sanitizePrintLayout({ ...current, marginMm: Number(event.target.value) }),
            )
          }
        />
      </label>
      <button className="quiet-button" type="button" onClick={handlePrint}>
        승인 자료 PDF·인쇄
      </button>
      <span>승인된 자료만 인쇄 화면에 포함됩니다.</span>
    </aside>
  );
}

export default PrintApprovedMaterials;
