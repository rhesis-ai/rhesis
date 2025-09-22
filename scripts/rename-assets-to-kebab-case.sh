#!/bin/bash

# Asset Renaming Script - Convert to kebab-case
# This script renames all public assets to follow kebab-case convention

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Base directory
BASE_DIR="/home/nicolaibohn/rhesis"

echo -e "${BLUE}🔄 Starting asset renaming to kebab-case...${NC}"
echo ""

# Function to rename a file and track changes
rename_file() {
    local old_path="$1"
    local new_path="$2"
    
    if [ "$old_path" != "$new_path" ] && [ -f "$old_path" ]; then
        echo -e "${YELLOW}Renaming:${NC}"
        echo -e "  From: ${old_path##*/}"
        echo -e "  To:   ${new_path##*/}"
        
        # Create directory if it doesn't exist
        mkdir -p "$(dirname "$new_path")"
        
        # Rename the file
        mv "$old_path" "$new_path"
        echo -e "${GREEN}✓ Renamed successfully${NC}"
        echo ""
        
        # Track the change for later reference updates
        echo "$old_path -> $new_path" >> "$BASE_DIR/asset_renames.log"
    fi
}

# Create log file for tracking renames
echo "# Asset Rename Log - $(date)" > "$BASE_DIR/asset_renames.log"
echo "# Format: old_path -> new_path" >> "$BASE_DIR/asset_renames.log"
echo "" >> "$BASE_DIR/asset_renames.log"

echo -e "${BLUE}📁 Processing Frontend Assets...${NC}"
echo ""

# Frontend - Brand Elements (24 files)
FRONTEND_ELEMENTS_DIR="$BASE_DIR/apps/frontend/public/elements"
for i in {1..24}; do
    old_file="$FRONTEND_ELEMENTS_DIR/Rhesis AI_brand elements${i}.svg"
    new_file="$FRONTEND_ELEMENTS_DIR/rhesis-brand-element-$(printf "%02d" $i).svg"
    rename_file "$old_file" "$new_file"
done

# Frontend - Logo Files
FRONTEND_LOGOS_DIR="$BASE_DIR/apps/frontend/public/logos"

# Logos with complex names
rename_file "$FRONTEND_LOGOS_DIR/Rhesis AI_Logo_RGB_Website logo.png" "$FRONTEND_LOGOS_DIR/rhesis-logo-website.png"
rename_file "$FRONTEND_LOGOS_DIR/Rhesis AI_Logo_RGB_Website logo_white.png" "$FRONTEND_LOGOS_DIR/rhesis-logo-website-white.png"
rename_file "$FRONTEND_LOGOS_DIR/Rhesis AI_Logo_RGB_Favicon.svg" "$FRONTEND_LOGOS_DIR/rhesis-logo-favicon.svg"
rename_file "$FRONTEND_LOGOS_DIR/Rhesis AI_Logo_Increased_Platypus.png" "$FRONTEND_LOGOS_DIR/rhesis-logo-platypus.png"
rename_file "$FRONTEND_LOGOS_DIR/Rhesis AI_Logo_Increased_Platypus_Darkmode.png" "$FRONTEND_LOGOS_DIR/rhesis-logo-platypus-dark.png"
rename_file "$FRONTEND_LOGOS_DIR/Rhesis AI_Logo_Increased_Platypus_Darkmode_White.png" "$FRONTEND_LOGOS_DIR/rhesis-logo-platypus-dark-white.png"

# Frontend - Font Files
FRONTEND_FONTS_DIR="$BASE_DIR/apps/frontend/public/fonts"

# Rename Be_Vietnam_Pro directory and files
if [ -d "$FRONTEND_FONTS_DIR/Be_Vietnam_Pro" ]; then
    mv "$FRONTEND_FONTS_DIR/Be_Vietnam_Pro" "$FRONTEND_FONTS_DIR/be-vietnam-pro"
    echo -e "${GREEN}✓ Renamed directory: Be_Vietnam_Pro -> be-vietnam-pro${NC}"
fi

# Rename Be Vietnam Pro font files
BE_VIETNAM_DIR="$FRONTEND_FONTS_DIR/be-vietnam-pro"
if [ -d "$BE_VIETNAM_DIR" ]; then
    for font_file in "$BE_VIETNAM_DIR"/BeVietnamPro-*.ttf; do
        if [ -f "$font_file" ]; then
            filename=$(basename "$font_file")
            # Convert BeVietnamPro-Bold.ttf to be-vietnam-pro-bold.ttf
            new_name=$(echo "$filename" | sed 's/BeVietnamPro-/be-vietnam-pro-/' | tr '[:upper:]' '[:lower:]')
            rename_file "$font_file" "$BE_VIETNAM_DIR/$new_name"
        fi
    done
fi

# Rename Sora directory and files to lowercase
if [ -d "$FRONTEND_FONTS_DIR/Sora" ]; then
    mv "$FRONTEND_FONTS_DIR/Sora" "$FRONTEND_FONTS_DIR/sora"
    echo -e "${GREEN}✓ Renamed directory: Sora -> sora${NC}"
fi

# Rename Sora font files
SORA_DIR="$FRONTEND_FONTS_DIR/sora"
if [ -d "$SORA_DIR" ]; then
    for font_file in "$SORA_DIR"/Sora-*.ttf; do
        if [ -f "$font_file" ]; then
            filename=$(basename "$font_file")
            # Convert Sora-Bold.ttf to sora-bold.ttf
            new_name=$(echo "$filename" | tr '[:upper:]' '[:lower:]')
            rename_file "$font_file" "$SORA_DIR/$new_name"
        fi
    done
fi

echo -e "${BLUE}📁 Processing Documentation Assets...${NC}"
echo ""

# Documentation - Logo Files
DOC_PUBLIC_DIR="$BASE_DIR/apps/documentation/public"

rename_file "$DOC_PUBLIC_DIR/Rhesis AI_Logo_RGB_Website logo.png" "$DOC_PUBLIC_DIR/rhesis-logo-website.png"
rename_file "$DOC_PUBLIC_DIR/Rhesis AI_Logo_RGB_Website logo_white.png" "$DOC_PUBLIC_DIR/rhesis-logo-website-white.png"
rename_file "$DOC_PUBLIC_DIR/Rhesis AI_Logo_RGB_Favicon.svg" "$DOC_PUBLIC_DIR/rhesis-logo-favicon.svg"
rename_file "$DOC_PUBLIC_DIR/Rhesis AI_Logo_RGB_Favicon_white.svg" "$DOC_PUBLIC_DIR/rhesis-logo-favicon-white.svg"

# Documentation - Typography/Font Files
DOC_TYPOGRAPHY_DIR="$DOC_PUBLIC_DIR/Typography"

# Rename Typography directory to fonts
if [ -d "$DOC_TYPOGRAPHY_DIR" ]; then
    mv "$DOC_TYPOGRAPHY_DIR" "$DOC_PUBLIC_DIR/fonts"
    echo -e "${GREEN}✓ Renamed directory: Typography -> fonts${NC}"
fi

DOC_FONTS_DIR="$DOC_PUBLIC_DIR/fonts"

# Rename Be_Vietnam_Pro directory and files
if [ -d "$DOC_FONTS_DIR/Be_Vietnam_Pro" ]; then
    mv "$DOC_FONTS_DIR/Be_Vietnam_Pro" "$DOC_FONTS_DIR/be-vietnam-pro"
    echo -e "${GREEN}✓ Renamed directory: Be_Vietnam_Pro -> be-vietnam-pro${NC}"
fi

# Rename Be Vietnam Pro font files in documentation
BE_VIETNAM_DOC_DIR="$DOC_FONTS_DIR/be-vietnam-pro"
if [ -d "$BE_VIETNAM_DOC_DIR" ]; then
    for font_file in "$BE_VIETNAM_DOC_DIR"/BeVietnamPro-*.ttf; do
        if [ -f "$font_file" ]; then
            filename=$(basename "$font_file")
            new_name=$(echo "$filename" | sed 's/BeVietnamPro-/be-vietnam-pro-/' | tr '[:upper:]' '[:lower:]')
            rename_file "$font_file" "$BE_VIETNAM_DOC_DIR/$new_name"
        fi
    done
fi

# Rename Sora directory and files in documentation
if [ -d "$DOC_FONTS_DIR/Sora" ]; then
    mv "$DOC_FONTS_DIR/Sora" "$DOC_FONTS_DIR/sora"
    echo -e "${GREEN}✓ Renamed directory: Sora -> sora${NC}"
fi

# Rename Sora font files in documentation
SORA_DOC_DIR="$DOC_FONTS_DIR/sora"
if [ -d "$SORA_DOC_DIR" ]; then
    for font_file in "$SORA_DOC_DIR"/Sora-*.ttf; do
        if [ -f "$font_file" ]; then
            filename=$(basename "$font_file")
            new_name=$(echo "$filename" | tr '[:upper:]' '[:lower:]')
            rename_file "$font_file" "$SORA_DOC_DIR/$new_name"
        fi
    done
fi

echo -e "${GREEN}✅ Asset renaming completed!${NC}"
echo ""
echo -e "${BLUE}📋 Summary:${NC}"
echo -e "  • All brand elements renamed to: rhesis-brand-element-01.svg, rhesis-brand-element-02.svg, etc."
echo -e "  • Logo files renamed to descriptive kebab-case names"
echo -e "  • Font directories renamed: Be_Vietnam_Pro -> be-vietnam-pro, Sora -> sora"
echo -e "  • Font files renamed to kebab-case"
echo -e "  • Documentation Typography directory renamed to fonts"
echo ""
echo -e "${YELLOW}⚠️  Next Steps:${NC}"
echo -e "  1. Update code references to use new asset paths"
echo -e "  2. Check the asset_renames.log file for a complete list of changes"
echo -e "  3. Test your applications to ensure all assets load correctly"
echo ""
echo -e "${BLUE}📄 Rename log saved to: $BASE_DIR/asset_renames.log${NC}"
