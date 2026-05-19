# Figma UI Revamp Audit

**File**: [Frontend](https://www.figma.com/design/RCN0J2AjA0UlStdPpdjUCu/Frontend)
**File Key**: `RCN0J2AjA0UlStdPpdjUCu`
**Audited**: 2026-05-19

---

## A. Foundations

### A1. Greyscale Colour Tokens (node `802:30139`)

| Token            | CSS Var                            | Hex       | Usage                          |
| ---------------- | ---------------------------------- | --------- | ------------------------------ |
| surface/subtle   | `--greyscale/surface/subtle`       | `#f9f9fa` | Page background light tint     |
| surface/default  | `--greyscale/surface/default`      | `#f3f4f6` | Table header background        |
| surface/disabled | `--greyscale/surface/disabled`     | `#cdd2da` | Disabled surface, input border |
| border/default   | `--greyscale/border/default`       | `#c1c7d1` | Default divider/border         |
| border/disabled  | `--greyscale/border/disabled`      | `#cdd2da` | Disabled border                |
| border/darker    | `--greyscale/border/darker`        | `#b6bdc9` | Stronger border                |
| text/title       | `--greyscale/text---icon/title`    | `#1a1c20` | H1-H6 headings                 |
| text/body        | `--greyscale/text---icon/body`     | `#2a2e36` | Body copy, cell text           |
| text/subtitle    | `--greyscale/text---icon/subtitle` | `#7f8a9b` | Category labels, subdued text  |
| text/caption     | `--greyscale/text---icon/caption`  | `#b6bdc9` | Caption / helper text          |
| text/negative    | `--greyscale/text---icon/negative` | `#f9f9fa` | Text on dark fills             |
| text/disabled    | `--greyscale/text---icon/disabled` | `#cdd2da` | Disabled text/icon             |
| text/white       | `--greyscale/text---icon/white`    | `#ffffff` | White                          |

**MUI greyscale ramp mapped in `theme.ts`:**
| Name | Hex |
|------|-----|
| `title` | `#1a1c20` |
| `body` | `#2a2e36` |
| `subtitle` | `#7f8a9b` |
| `border` | `#cdd2da` |
| `surface1` | `#f7f8f9` |
| `surface2` | `#eef0f3` |

### A2. Dark Mode Colour Tokens (node `1200:23`)

Dark mode uses the existing Rhesis dark palette from `theme.ts`. The greyscale ramp in dark:
| Name | Hex |
|------|-----|
| `title` | `#e6edf3` |
| `body` | `#c9d1d9` |
| `subtitle` | `#8b949e` |
| `border` | `#30363d` |
| `surface1` | `#161b22` |
| `surface2` | `#0d1117` |

### A3. Typography Scale (node `802:30265`)

All body text uses **Be Vietnam Pro**; technical/mono variants use **Sometype Mono**.

| Variant       | Size | Line Height | Weight         | MUI Name      |
| ------------- | ---- | ----------- | -------------- | ------------- |
| H1/Bold       | 48px | 57.6px      | 800            | `h1`          |
| H2/Bold       | 40px | 48px        | 800            | `h2`          |
| H3/Bold       | 33px | 39.6px      | 800            | `h3`          |
| H4/Bold       | 28px | 33.6px      | 700            | `h4`          |
| H5/Bold       | 23px | 27.6px      | 700            | `h5`          |
| H6/Bold       | 20px | 24px        | 600            | `h6`          |
| Body L/Reg    | 16px | 24px        | 400            | `bodyLReg`    |
| Body M/Reg    | 14px | 22px        | 400            | `bodyMReg`    |
| Body M/Bold   | 14px | 22px        | 700            | `bodyMBold`   |
| Body S/Reg    | 12px | 18px        | 400            | `bodySReg`    |
| Caption/Bold  | 12px | 18px        | 600            | `captionBold` |
| Caption/Reg   | 12px | 18px        | 400            | `caption`     |
| Overline/Bold | 12px | 18px        | 600, uppercase | `overline`    |

### A4. Elevation Scale (node `802:30375`)

| Level | Box Shadow                                                                         |
| ----- | ---------------------------------------------------------------------------------- |
| XS    | `0px 2px 4px rgba(84, 90, 101, 0.25)`                                              |
| S     | `0px 16px 32px -4px rgba(84, 90, 101, 0.10), 0px 4px 4px rgba(84, 90, 101, 0.04)`  |
| M     | `0px 24px 48px -8px rgba(84, 90, 101, 0.12), 0px 4px 4px rgba(84, 90, 101, 0.04)`  |
| L     | `0px 40px 80px -16px rgba(84, 90, 101, 0.18), 0px 4px 4px rgba(84, 90, 101, 0.04)` |
| XL    | `0px 56px 112px -20px rgba(0, 0, 0, 0.25), 0px 4px 4px rgba(84, 90, 101, 0.04)`    |

---

## B. Component Library

| Figma Component  | Current Code Equivalent              | Notes                                |
| ---------------- | ------------------------------------ | ------------------------------------ |
| Button / Default | `MuiButton` (theme overrides)        | Add `pill` variant                   |
| Pill Button      | `MuiButton` pill variant             | borderRadius 999, new in Phase 1     |
| FAB              | — (new)                              | New `components/common/Fab.tsx`      |
| Searchfield      | `SearchAndFilterBar.tsx`             | Update border-radius to 8px          |
| Breadcrumbs      | MUI `Breadcrumbs` (per-page)         | Check for shared wrapper             |
| Nav item         | `DashboardLayout` nav item           | Replace with `Sidebar.tsx`           |
| Nav company      | `SidebarFooter.tsx` partial          | Move to `Sidebar.tsx` brand block    |
| Nav category     | `DashboardLayout` section headers    | Custom in `Sidebar.tsx`              |
| Nav avatar       | `UserAvatar.tsx`                     | Keep, wire into `Sidebar.tsx` footer |
| TableHeadRow     | `BaseTable.tsx` / `BaseDataGrid.tsx` | Update styles in Phase 3b            |
| Table_row        | `BaseTable.tsx` / `BaseDataGrid.tsx` | 48px height, hover actions           |
| Badge            | `BaseTag.tsx`, `StatusChip.tsx`      | borderRadius 999, Phase 3a           |
| Pagination       | MUI Pagination (in BaseDataGrid)     | Inherit from theme                   |
| Toolbar          | `ActionBar.tsx` partial              | Replace with new `Toolbar.tsx`       |
| Drawer           | `BaseDrawer.tsx`                     | Update width/padding in Phase 3b     |

---

## C. Screens

| Figma Node  | Section              | Description                           | Target Page                  |
| ----------- | -------------------- | ------------------------------------- | ---------------------------- |
| `841:38312` | DESIGN Overview      | Overview Table View (reference)       | Any list `page.tsx`          |
| `841:38413` | NAVI                 | Sidebar / navigation rail             | `layout.tsx` → `Sidebar.tsx` |
| `841:38314` | CONTENT              | Main content area                     | `AppShell.tsx`               |
| `841:38313` | DESIGN Drawer_Filter | Filter drawer pattern                 | `BaseDrawer.tsx`             |
| `841:38320` | Top bar              | Breadcrumbs + title + FAB cluster     | `AppShell.tsx` topBar slot   |
| `841:38328` | Toolbar              | Filter + search + pill tabs + actions | `Toolbar.tsx`                |

### Overview Table View layout (node `841:38312`)

The reference screen establishes the canonical list-page pattern:

```
[Sidebar 240px] | [Content area]
                |   [Breadcrumbs] [Breadcrumb] > [Breadcrumb]
                |   [H4 title]                    [Download FAB] [Add FAB]
                |   [Body L description text]
                |
                |   [Paper card – full width, xs elevation]
                |     [Toolbar: filter icon | search | pill tabs ... | Columns Density Export]
                |     [Table header row – surface1 bg, 48px, 14px semibold]
                |     [Table rows – 48px, border-bottom #cdd2da]
                |       [Cell text 14px body] ... [Badge] [Badge] [edit/delete on hover]
                |     [Pagination: rows per page + prev/next]
```

**Sidebar structure (node `841:38413`):**

- Width: 240px, white bg (dark: `#161B22`)
- Top: brand block (logo + "Rhesis AI" 18px/bold + caret)
- Middle: scrollable nav groups
  - Category labels: 12px/semibold, `#7f8a9b`, uppercase
  - Nav items: 40px height, icon (24px) + label (14px)
  - Selected: `primary.dark` bg, white text/icon
  - Hover: `surface1` bg
- Bottom pinned: "Star Rhesis" item, "Support" item, `UserAvatar` (avatar + name + email)
- Collapse toggle: absolute button at top-right edge

**Toolbar pattern (node `841:38328`):**

- Left: filter icon button + Searchfield
- Middle: Pill Button group (Label | Label | Label)
- Right: Columns | Density | Export icon+text buttons
- Height: 38px, full-width flex `space-between`
