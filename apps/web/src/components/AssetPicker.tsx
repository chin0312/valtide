import { useEffect, useMemo, useRef, useState } from "react";

type AssetPickerOption = {
  asset: string;
  operational_ready?: boolean;
};

const ASSET_DISPLAY_NAMES: Record<string, string> = {
  NVDAx: "NVIDIA Tokenized Equity",
  SPYx: "S&P 500 Tokenized ETF",
  QQQx: "Nasdaq-100 Tokenized ETF",
  AAPLx: "Apple Tokenized Equity",
};

export function assetDisplayName(asset: string): string {
  return ASSET_DISPLAY_NAMES[asset] ?? "Tokenized equity";
}

export function assetAvailabilityLabel(operationalReady: boolean | undefined): string {
  if (operationalReady === undefined) return "Checking";
  return operationalReady ? "Available" : "Coming soon";
}

export function AssetPicker({ assets, selectedAsset, onChange }: {
  assets: AssetPickerOption[];
  selectedAsset: string;
  onChange: (asset: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlighted, setHighlighted] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const options = assets.length ? assets : [{ asset: selectedAsset }];
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return options;
    return options.filter(({ asset }) => `${asset} ${assetDisplayName(asset)}`.toLowerCase().includes(needle));
  }, [options, query]);

  useEffect(() => {
    if (!open) return;
    const focus = window.requestAnimationFrame(() => searchRef.current?.focus());
    const closeOnOutsideClick = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    };
    document.addEventListener("pointerdown", closeOnOutsideClick);
    return () => {
      window.cancelAnimationFrame(focus);
      document.removeEventListener("pointerdown", closeOnOutsideClick);
    };
  }, [open]);

  useEffect(() => setHighlighted(0), [query]);

  const close = (restoreFocus = false) => {
    setOpen(false);
    setQuery("");
    if (restoreFocus) window.requestAnimationFrame(() => triggerRef.current?.focus());
  };

  const choose = (asset: string) => {
    onChange(asset);
    close(true);
  };

  const handleSearchKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close(true);
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlighted((index) => Math.min(index + 1, Math.max(0, filtered.length - 1)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlighted((index) => Math.max(0, index - 1));
    } else if (event.key === "Enter" && filtered[highlighted]) {
      event.preventDefault();
      choose(filtered[highlighted].asset);
    }
  };

  return <div className="asset-picker" ref={rootRef}>
    <span className="asset-picker__label">Asset</span>
    <button
      ref={triggerRef}
      type="button"
      className="asset-picker__trigger"
      aria-label={`Selected asset: ${selectedAsset}`}
      aria-haspopup="listbox"
      aria-expanded={open}
      aria-controls="asset-picker-listbox"
      onClick={() => open ? close() : setOpen(true)}
    >
      <span>{selectedAsset}</span><span className="asset-picker__chevron" aria-hidden="true">⌄</span>
    </button>
    <div className="asset-picker__popover" hidden={!open}>
      <input
        ref={searchRef}
        className="asset-picker__search"
        type="search"
        role="combobox"
        value={query}
        aria-label="Search assets"
        aria-autocomplete="list"
        aria-controls="asset-picker-listbox"
        aria-expanded="true"
        aria-activedescendant={filtered[highlighted] ? `asset-option-${filtered[highlighted].asset}` : undefined}
        placeholder="Search assets…"
        onChange={(event) => setQuery(event.target.value)}
        onKeyDown={handleSearchKeyDown}
      />
      <div id="asset-picker-listbox" className="asset-picker__list" role="listbox" aria-label="Available assets">
        {filtered.map((option, index) => <button
          type="button"
          role="option"
          id={`asset-option-${option.asset}`}
          aria-selected={option.asset === selectedAsset}
          className={`asset-picker__option ${index === highlighted ? "is-highlighted" : ""}`}
          key={option.asset}
          onMouseEnter={() => setHighlighted(index)}
          onClick={() => choose(option.asset)}
        >
          <span><strong>{option.asset}</strong><small>{assetDisplayName(option.asset)}</small></span>
          <em className={option.operational_ready ? "is-available" : ""}>{assetAvailabilityLabel(option.operational_ready)}</em>
        </button>)}
        {!filtered.length && <p className="asset-picker__empty">No assets match “{query}”.</p>}
      </div>
    </div>
  </div>;
}
