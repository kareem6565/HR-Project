import React from "react";
import { useThemeMode } from "../../context/ThemeContext";
import AnimatedHeraMark from "../brand/AnimatedHeraMark";

export default function BrandIcon() {
  const theme = useThemeMode();
  const variant = theme === "dark" ? "dark" : "light";

  return (
    <span className="brand-image" aria-hidden="true">
      <AnimatedHeraMark size={38} variant={variant} />
    </span>
  );
}
