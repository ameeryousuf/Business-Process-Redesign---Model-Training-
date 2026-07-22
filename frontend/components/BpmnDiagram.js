"use client";
import { useEffect, useRef } from "react";
import BpmnJS from "bpmn-js/lib/Viewer";

export default function BpmnDiagram({ xml, height = 400 }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || !xml) return;

    let isCancelled = false;
    const viewer = new BpmnJS({ container: containerRef.current });

    const importDone = viewer.importXML(xml)
      .then(() => {
        if (isCancelled) return;
        viewer.get("canvas").zoom("fit-viewport", { x: 40, y: 40 });
      })
      .catch((err) => {
        if (isCancelled) return;
        console.error("Error rendering BPMN diagram:", err);
      });

    return () => {
      isCancelled = true;
      importDone.finally(() => viewer.destroy());
    };
  }, [xml]);

  return (
    <div
      style={{
        padding: "16px",
        background: "#fcfcfd",
        border: "1px solid var(--panel-border)",
        borderRadius: "12px",
      }}
    >
      <div ref={containerRef} style={{ height: `${height}px` }} />
    </div>
  );
}