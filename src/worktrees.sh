#!/bin/bash

# Manage git worktrees for parallel agentic workflows in otr-web.
#
# Usage:
#   worktrees.sh setup [count]     Create worktrees with fresh branches off master
#   worktrees.sh teardown [count]  Remove worktrees and delete wt-* branches
#   worktrees.sh reset [count]     Teardown + setup (fresh start)
#
# Arguments:
#   count   Number of worktrees (default: 3)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OTR_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
MAIN_WORKTREE="$OTR_DIR/otr-web"
DEFAULT_COUNT=3

setup() {
    local count="${1:-$DEFAULT_COUNT}"

    if [ ! -d "$MAIN_WORKTREE/.git" ]; then
        echo "Error: Main worktree not found at $MAIN_WORKTREE"
        exit 1
    fi

    echo "Pruning stale worktree references..."
    git -C "$MAIN_WORKTREE" worktree prune

    echo "Creating $count worktrees off master..."
    for i in $(seq 1 "$count"); do
        local wt_dir="$OTR_DIR/otr-web-$i"
        local branch="wt-$i"

        if [ -d "$wt_dir" ]; then
            echo "  Skipping otr-web-$i (already exists)"
            continue
        fi

        # Delete branch if it exists (leftover from previous run)
        git -C "$MAIN_WORKTREE" branch -D "$branch" 2>/dev/null || true

        git -C "$MAIN_WORKTREE" worktree add "$wt_dir" -b "$branch" master
        echo "  Created otr-web-$i on branch $branch"
    done

    echo "Symlinking .env..."
    for i in $(seq 1 "$count"); do
        local wt_dir="$OTR_DIR/otr-web-$i"
        if [ ! -L "$wt_dir/.env" ] && [ ! -f "$wt_dir/.env" ]; then
            ln -s ../otr-web/.env "$wt_dir/.env"
            echo "  Linked otr-web-$i/.env"
        else
            echo "  Skipping otr-web-$i/.env (already exists)"
        fi
    done

    if [ -d "$MAIN_WORKTREE/.claude" ]; then
        echo "Copying .claude/ settings..."
        for i in $(seq 1 "$count"); do
            local wt_dir="$OTR_DIR/otr-web-$i"
            if [ -d "$wt_dir/.claude" ]; then
                echo "  Skipping otr-web-$i/.claude (already exists)"
            else
                cp -r "$MAIN_WORKTREE/.claude" "$wt_dir/.claude"
                echo "  Copied .claude/ to otr-web-$i"
            fi
        done
    fi

    echo "Installing dependencies in parallel..."
    local pids=()
    for i in $(seq 1 "$count"); do
        local wt_dir="$OTR_DIR/otr-web-$i"
        (cd "$wt_dir" && bun install --silent) &
        pids+=($!)
        echo "  Started bun install for otr-web-$i (PID $!)"
    done

    local failed=0
    for pid in "${pids[@]}"; do
        if ! wait "$pid"; then
            failed=$((failed + 1))
        fi
    done

    if [ "$failed" -gt 0 ]; then
        echo "Warning: $failed install(s) failed"
    else
        echo "All installs completed successfully"
    fi

    echo ""
    echo "Worktrees ready:"
    git -C "$MAIN_WORKTREE" worktree list
}

teardown() {
    local count="${1:-$DEFAULT_COUNT}"

    echo "Removing $count worktrees..."
    for i in $(seq 1 "$count"); do
        local wt_dir="$OTR_DIR/otr-web-$i"
        local branch="wt-$i"

        if [ -d "$wt_dir" ]; then
            git -C "$MAIN_WORKTREE" worktree remove "$wt_dir" --force 2>/dev/null || {
                echo "  Force-removing directory otr-web-$i..."
                rm -rf "$wt_dir"
            }
            echo "  Removed otr-web-$i"
        fi

        # Delete the branch
        git -C "$MAIN_WORKTREE" branch -D "$branch" 2>/dev/null && \
            echo "  Deleted branch $branch" || true
    done

    git -C "$MAIN_WORKTREE" worktree prune
    echo "Teardown complete"
}

reset() {
    local count="${1:-$DEFAULT_COUNT}"

    # Find the highest existing worktree index so extras get cleaned up
    local max_existing=0
    for dir in "$OTR_DIR"/otr-web-[0-9]*; do
        [ -d "$dir" ] || continue
        local num="${dir##*otr-web-}"
        if [[ "$num" =~ ^[0-9]+$ ]] && [ "$num" -gt "$max_existing" ]; then
            max_existing="$num"
        fi
    done

    # Teardown whichever is larger: requested count or existing count
    local teardown_count=$(( count > max_existing ? count : max_existing ))
    teardown "$teardown_count"
    echo ""
    setup "$count"
}

# --- Main ---

command="${1:-}"
count="${2:-$DEFAULT_COUNT}"

case "$command" in
    setup)
        setup "$count"
        ;;
    teardown)
        teardown "$count"
        ;;
    reset)
        reset "$count"
        ;;
    *)
        echo "Usage: $(basename "$0") {setup|teardown|reset} [count]"
        echo ""
        echo "Commands:"
        echo "  setup [count]     Create worktrees (default: $DEFAULT_COUNT)"
        echo "  teardown [count]  Remove worktrees and branches"
        echo "  reset [count]     Teardown + setup"
        exit 1
        ;;
esac
