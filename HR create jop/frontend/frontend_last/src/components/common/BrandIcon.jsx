import React from "react";
import { useThemeMode } from "../../context/ThemeContext";

export default function BrandIcon() {
  const theme = useThemeMode();
  const icon = theme === "dark" ? "dark" : "light";

  return <img className="brand-image" src={`/brand/hera-icon-${icon}.svg`} alt="HERA" />;
}
