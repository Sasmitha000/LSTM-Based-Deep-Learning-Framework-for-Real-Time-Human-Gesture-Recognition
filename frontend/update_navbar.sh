#!/bin/bash

# List of HTML files to update
files=(
    "index.html"
    "detection.html"
    "learning.html"
    "dashboard.html"
    "user-dashboard.html"
    "get-api-key.html"
    "api-docs.html"
    "privacy.html"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "Updating $file..."
        
        # Add hamburger menu button after opening <body> tag
        # And add overlay div before closing </body> tag
        
        # This is a simple approach - add the elements if they don't exist
        if ! grep -q "hamburger" "$file"; then
            # Add hamburger after <body> or after <body class="...">
            sed -i '' '/<body[^>]*>/a\
    <!-- Mobile Hamburger Menu -->\
    <div class="hamburger" onclick="toggleMobileMenu()">\
        <span></span>\
        <span></span>\
        <span></span>\
    </div>\
    <div class="nav-overlay" onclick="toggleMobileMenu()"></div>
' "$file"
        fi
        
        echo "✅ Updated $file"
    fi
done

echo ""
echo "✅ All files updated!"
