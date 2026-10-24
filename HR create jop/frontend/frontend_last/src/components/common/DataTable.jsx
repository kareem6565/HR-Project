import React from "react";

// Generic table with accessible keyboard interaction (UI-01).
// `columns` is [{ key, header, render? }], `data` is an array of row objects.
// Pass onRowClick to make rows focusable (tabIndex=0) and operable with Enter/Space keys
// while preserving valid semantic table structure.
export default function DataTable({
  columns,
  data,
  onRowClick,
  emptyLabel = "No data found.",
  emptyAction,
  header,
}) {
  return (
    <div className="panel table-panel">
      {header}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.key} scope="col">{col.header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr
                key={row.id ?? i}
                className={onRowClick ? "clickable" : ""}
                tabIndex={onRowClick ? 0 : undefined}
                onClick={() => onRowClick?.(row)}
                onKeyDown={(e) => {
                  if (onRowClick && (e.key === "Enter" || e.key === " ")) {
                    if (e.target.tagName === "BUTTON" || e.target.tagName === "A") return;
                    e.preventDefault();
                    onRowClick(row);
                  }
                }}
              >
                {columns.map((col) => (
                  <td key={col.key}>{col.render ? col.render(row) : row[col.key]}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!data.length && (
        <div className="empty">
          {emptyLabel}
          {emptyAction}
        </div>
      )}
    </div>
  );
}
