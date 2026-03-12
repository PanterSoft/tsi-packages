#!/bin/bash
# Test script for version discovery workflow
# This simulates what the GitHub Actions workflow does

set -e

echo "🧪 Testing Version Discovery Workflow"
echo "======================================"
echo ""

# Check if we're in the right directory
if [ ! -d "packages" ]; then
    echo "❌ Error: packages directory not found. Run this from the repository root."
    exit 1
fi

# Check if script exists
if [ ! -f "scripts/discover-versions.py" ]; then
    echo "❌ Error: discover-versions.py not found"
    exit 1
fi

# Test 1: Single package discovery (dry run)
echo "📦 Test 1: Single package discovery (dry run)"
echo "----------------------------------------------"
python3 scripts/discover-versions.py curl --dry-run --max-versions 3
echo ""

# Test 2: Check if script accepts GitHub token
echo "📦 Test 2: GitHub token support"
echo "----------------------------------------------"
if [ -n "$GITHUB_TOKEN" ]; then
    echo "✅ GITHUB_TOKEN is set"
    python3 scripts/discover-versions.py curl --dry-run --max-versions 2 --github-token "$GITHUB_TOKEN" 2>&1 | head -5
else
    echo "⚠️  GITHUB_TOKEN not set (this is OK for local testing)"
    echo "   The workflow will use secrets.GITHUB_TOKEN automatically"
fi
echo ""

# Test 3: Test argument handling (simulate workflow)
echo "📦 Test 3: Workflow argument simulation"
echo "----------------------------------------------"
PACKAGE=""
MAX_VERSIONS=""
CMD_ARGS=()

if [ -n "${PACKAGE}" ]; then
    CMD_ARGS+=("${PACKAGE}")
else
    CMD_ARGS+=("--all")
fi

if [ -n "${MAX_VERSIONS}" ]; then
    CMD_ARGS+=("--max-versions" "${MAX_VERSIONS}")
fi

CMD_ARGS+=("--packages-dir" "packages")
CMD_ARGS+=("--dry-run")
CMD_ARGS+=("--max-versions" "2")  # Limit for testing

echo "Command: python3 scripts/discover-versions.py ${CMD_ARGS[*]}"
python3 scripts/discover-versions.py "${CMD_ARGS[@]}" 2>&1 | head -20
echo ""

# Test 4: Check workflow file syntax
echo "📦 Test 4: Workflow file check"
echo "----------------------------------------------"
if [ -f ".github/workflows/discover-versions.yml" ]; then
    echo "✅ Workflow file exists"
    # Check for common YAML issues
    if grep -q "GITHUB_TOKEN" .github/workflows/discover-versions.yml; then
        echo "✅ GITHUB_TOKEN is configured"
    else
        echo "❌ GITHUB_TOKEN not found in workflow"
    fi
    if grep -q "CMD_ARGS" .github/workflows/discover-versions.yml; then
        echo "✅ Uses CMD_ARGS array (proper argument handling)"
    fi
else
    echo "❌ Workflow file not found"
fi
echo ""

echo "✅ All tests completed!"
echo ""
echo "To trigger the workflow on GitHub:"
echo "1. Go to: https://github.com/YOUR_REPO/actions/workflows/discover-versions.yml"
echo "2. Click 'Run workflow'"
echo "3. Leave 'package' empty to check all packages"
echo "4. Leave 'max_versions' empty to discover all versions"
echo "5. Click 'Run workflow'"

