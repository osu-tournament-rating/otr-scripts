#!/bin/bash

set -euo pipefail

# Configuration - modify these paths as needed
readonly API_DIR="${API_DIR:-$HOME/Documents/code/git/otr-api/API}"
readonly CLIENTS_DIR="${CLIENTS_DIR:-$HOME/Documents/code/git/otr-api-clients}"
readonly TS_CLIENT_DIR="${TS_CLIENT_DIR:-$CLIENTS_DIR/src/ts}"
readonly SWAGGER_OUTPUT_PATH="${API_DIR}/bin/Debug/net9.0/swagger.json"

# Color codes
readonly CYAN='\033[0;36m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly MAGENTA='\033[0;35m'
readonly RED='\033[0;31m'
readonly BOLD='\033[1m'
readonly RESET='\033[0m'

# Global flags for summary
VERSION_BUMPED=false
PUBLISHED_TO_NPM=false
PACKAGE_NAME=""    # Will be set if versioning occurs
NEW_VERSION=""     # Will be set if versioning occurs
confirm_process="" # Will store user's choice for versioning/publishing (y/N)

# Logging functions
log_info() {
  echo -e "${BOLD}${BLUE}==>${RESET} ${BOLD}$1${RESET}" >&2
}

log_success() {
  echo -e "${GREEN}✓ $1${RESET}" >&2
}

log_error() {
  echo -e "${RED}✗ Error: $1${RESET}" >&2
}

log_warning() {
  echo -e "${YELLOW}⚠ Warning: $1${RESET}" >&2
}

# Error handling
cleanup() {
  local exit_code=$?
  if [[ $exit_code -ne 0 ]]; then
    # Specific error messages should be printed by execute_step or other checks.
    # This is a fallback message.
    echo -e "${RED}Script encountered an error. Exit code: $exit_code${RESET}" >&2
    echo -e "${RED}Please check the messages above for details.${RESET}" >&2
  fi
  # 'trap EXIT' handles propagating the original exit code.
}

trap cleanup EXIT

# Validation functions
check_command() {
  if ! command -v "$1" &>/dev/null; then
    log_error "Required command '$1' not found. Please install it first."
    exit 1
  fi
}

check_directory() {
  if [[ ! -d "$1" ]]; then
    log_error "Directory does not exist: $1"
    exit 1
  fi
}

check_file() {
  if [[ ! -f "$1" ]]; then
    log_error "File does not exist: $1"
    exit 1
  fi
}

# Safe directory change with validation
safe_cd() {
  local target_dir="$1"
  check_directory "$target_dir"
  cd "$target_dir" || {
    log_error "Failed to change directory to: $target_dir"
    exit 1
  }
}

# Execute command with error handling
execute_step() {
  local description="$1"
  shift

  log_info "$description"

  if "$@"; then
    log_success "$description completed"
  else
    local cmd_exit_code=$?
    log_error "$description failed (exit code: $cmd_exit_code)"
    exit $cmd_exit_code # Propagate the specific exit code of the failed command
  fi
}

# Validation phase
validate_environment() {
  log_info "Validating environment"

  check_command "dotnet"
  check_command "nswag"
  check_command "npm"
  check_command "tsc"
  check_command "node" # Used for reading package.json properties

  check_directory "$API_DIR"
  check_directory "$CLIENTS_DIR"
  check_directory "$TS_CLIENT_DIR"
  check_file "$TS_CLIENT_DIR/package.json" # Crucial for versioning/publishing

  log_success "Environment validation passed"
}

# Main execution steps
install_dependencies() {
  safe_cd "$TS_CLIENT_DIR"
  execute_step "Installing npm dependencies in $TS_CLIENT_DIR" npm install
}

generate_swagger() {
  safe_cd "$API_DIR"
  execute_step "Generating Swagger file from $API_DIR" dotnet run --swagger-to-file
  check_file "$SWAGGER_OUTPUT_PATH"
}

copy_swagger() {
  local dest_dir="$CLIENTS_DIR/"
  check_directory "$dest_dir" # Should already exist and be checked
  execute_step "Copying swagger.json to $dest_dir" \
    cp "$SWAGGER_OUTPUT_PATH" "$dest_dir"
  check_file "$dest_dir/swagger.json"
}

run_nswag() {
  safe_cd "$CLIENTS_DIR"
  execute_step "Running NSwag code generation in $CLIENTS_DIR" nswag run
}

build_typescript_client() {
  safe_cd "$TS_CLIENT_DIR"
  execute_step "Building TypeScript client in $TS_CLIENT_DIR" npm run build
}

format_code() {
  safe_cd "$TS_CLIENT_DIR"
  execute_step "Formatting generated code in $TS_CLIENT_DIR" npm run format
}

handle_versioning_and_publishing() {
  log_info "Client Versioning and Publishing"
  safe_cd "$TS_CLIENT_DIR"

  # Get package name early
  if ! current_package_name=$(node -p "require('./package.json').name" 2>/dev/null); then
    log_error "Could not read package name from package.json in $TS_CLIENT_DIR"
    log_warning "Skipping versioning and publishing due to missing package name."
    PACKAGE_NAME="" # Ensure it's empty if we can't read it
    return          # Do not exit script, just skip this optional part
  fi
  PACKAGE_NAME="$current_package_name"

  # confirm_process is global, read directly into it
  read -r -p "$(echo -e "${YELLOW}??${RESET} Do you want to proceed with versioning and/or publishing for '${BOLD}$PACKAGE_NAME${RESET}'? (y/N) ")" confirm_process
  if [[ "${confirm_process,,}" != "y" ]]; then
    log_info "Versioning and publishing skipped by user."
    return
  fi

  local version_type=""
  local npm_version_args=() # Array to hold npm version arguments
  echo -e "${CYAN}Select version bump type for '${BOLD}$PACKAGE_NAME${RESET}':${RESET}"
  PS3="$(echo -e "${YELLOW}??${RESET} Enter number or type name: ")"
  select opt in "patch" "minor" "major" "prerelease" "skip bump"; do
    case $opt in
    "patch" | "minor" | "major")
      version_type=$opt
      npm_version_args=("$version_type")
      break
      ;;
    "prerelease")
      version_type=$opt
      local preid
      read -r -p "$(echo -e "${YELLOW}??${RESET} Enter prerelease identifier (e.g., dev, beta, rc - required): ")" preid
      preid=$(echo "$preid" | xargs) # Trim whitespace
      if [[ -z "$preid" ]]; then
        log_error "Prerelease identifier cannot be empty for 'prerelease' bump type."
        log_warning "Skipping version bump. You can try again or bump manually later."
        version_type="" # Reset to skip bump
        break
      fi
      npm_version_args=("$version_type" "--preid=$preid")
      break
      ;;
    "skip bump")
      log_info "Skipping version bump."
      version_type=""
      break
      ;;
    *)
      log_warning "Invalid option '$REPLY'. Please choose a number or type from the list."
      ;;
    esac
  done

  if [[ -n "$version_type" ]]; then
    execute_step "Bumping version (${npm_version_args[*]})" npm version "${npm_version_args[@]}"
    VERSION_BUMPED=true
    if ! new_pkg_version=$(node -p "require('./package.json').version" 2>/dev/null); then
      log_error "Could not read new version from package.json after bump."
      # NEW_VERSION will remain empty
    else
      NEW_VERSION="$new_pkg_version"
    fi
  fi

  local confirm_publish_prompt
  local version_to_publish_display
  if [[ "$VERSION_BUMPED" == true && -n "$NEW_VERSION" ]]; then
    version_to_publish_display="$NEW_VERSION"
    confirm_publish_prompt="$(echo -e "${YELLOW}??${RESET} Publish version ${BOLD}$version_to_publish_display${RESET} of '${BOLD}$PACKAGE_NAME${RESET}' to npm? (y/N) ")"
  elif [[ "$VERSION_BUMPED" == true ]]; then # Version bumped but NEW_VERSION couldn't be read
    version_to_publish_display="(newly bumped version)"
    confirm_publish_prompt="$(echo -e "${YELLOW}??${RESET} Publish the ${BOLD}$version_to_publish_display${RESET} of '${BOLD}$PACKAGE_NAME${RESET}' to npm? (y/N) ")"
  else
    # No bump, offer to publish current version
    local current_version_for_publish
    current_version_for_publish=$(node -p "require('./package.json').version" 2>/dev/null || echo "current")
    version_to_publish_display="$current_version_for_publish"
    confirm_publish_prompt="$(echo -e "${YELLOW}??${RESET} Publish version ${BOLD}$version_to_publish_display${RESET} of '${BOLD}$PACKAGE_NAME${RESET}' to npm? (y/N) ")"
    # If we publish without bumping, NEW_VERSION should reflect the published version
    if [[ -z "$NEW_VERSION" && "$current_version_for_publish" != "current" ]]; then
      NEW_VERSION="$current_version_for_publish"
    fi
  fi

  local do_publish_choice
  read -r -p "$confirm_publish_prompt" do_publish_choice
  if [[ "${do_publish_choice,,}" == "y" ]]; then
    # Determine if this is a pre-release version and extract the tag
    local npm_publish_args=()
    local version_to_check="${NEW_VERSION:-$(node -p "require('./package.json').version" 2>/dev/null)}"
    
    # Check if version contains a pre-release identifier (e.g., 1.0.0-dev.1, 2.1.0-beta.3)
    if [[ "$version_to_check" =~ ^[0-9]+\.[0-9]+\.[0-9]+-([a-zA-Z]+)(\.[0-9]+)?$ ]]; then
      local prerelease_tag="${BASH_REMATCH[1]}"
      npm_publish_args=("--tag" "$prerelease_tag")
      execute_step "Publishing '$PACKAGE_NAME' to npm with tag '$prerelease_tag'" npm publish "${npm_publish_args[@]}"
    else
      execute_step "Publishing '$PACKAGE_NAME' to npm" npm publish
    fi
    
    PUBLISHED_TO_NPM=true
    # If NEW_VERSION is empty here but we published, it implies current version was published
    log_success "'$PACKAGE_NAME'${NEW_VERSION:+@$NEW_VERSION} published successfully!"
  else
    log_info "Skipped publishing to npm."
  fi
}

# Display usage information
show_usage() {
  local default_api_dir="${API_DIR:-$HOME/Documents/code/git/otr-api/API}"
  local default_clients_dir="${CLIENTS_DIR:-$HOME/Documents/code/git/otr-api-clients}"
  local default_ts_client_dir="${TS_CLIENT_DIR:-$CLIENTS_DIR/src/ts}"

  cat <<EOF
Usage: $0 [OPTIONS]

OTR API Client Update Script

This script automates the process of updating API clients by:
1. Validating environment and prerequisites.
2. Installing npm dependencies for the TypeScript client.
3. Generating Swagger documentation from the API project.
4. Copying the Swagger file to the clients directory.
5. Running NSwag to generate client code from the Swagger file.
6. Building the TypeScript client.
7. Formatting the generated TypeScript code.
8. Optionally, prompting to bump the version of the TypeScript client and publish it to npm.

Prerequisites:
  - dotnet CLI (\`dotnet\`)
  - NSwag CLI (\`nswag\`)
  - Node.js (\`node\`) and npm (\`npm\`)
  - TypeScript compiler (\`tsc\`, usually via npm dependencies)
  - Your API project must be configured to generate a swagger.json file.
    (Default expected at: ${SWAGGER_OUTPUT_PATH})
  - Your TypeScript client project must have a package.json with \`build\` and \`format\` scripts.

Environment Variables:
  API_DIR        Path to the API directory (default: $default_api_dir)
  CLIENTS_DIR    Path to the clients directory (default: $default_clients_dir)
  TS_CLIENT_DIR  Path to the TypeScript client directory (default: $default_ts_client_dir)
  # SWAGGER_OUTPUT_PATH is derived from API_DIR but can be set if your API project
  # outputs swagger.json to a non-default location relative to API_DIR.

Options:
  -h, --help     Show this help message
  -v, --verbose  Enable verbose output (\`set -x\`)

Examples:
  $0                           # Run with default paths
  API_DIR=/custom/api/path $0  # Run with custom API directory
EOF
}

# Display completion summary
show_completion_summary() {
  echo
  log_success "OTR API client toolchain finished."
  echo
  echo -e "${BOLD}${MAGENTA}================== Summary ===================${RESET}"
  echo -e "${YELLOW}→${RESET} Client code updated in: ${CYAN}$TS_CLIENT_DIR${RESET}"

  if [[ -n "$PACKAGE_NAME" ]]; then # If we attempted versioning/publishing
    if [[ "$VERSION_BUMPED" == true && -n "$NEW_VERSION" ]]; then
      echo -e "${YELLOW}→${RESET} Package ${BOLD}'$PACKAGE_NAME'${RESET} version bumped to: ${CYAN}$NEW_VERSION${RESET}"
    elif [[ "$VERSION_BUMPED" == true ]]; then
      echo -e "${YELLOW}→${RESET} Package ${BOLD}'$PACKAGE_NAME'${RESET} version was bumped (new version string not captured)."
    fi

    if [[ "$PUBLISHED_TO_NPM" == true ]]; then
      local display_version="$NEW_VERSION"
      if [[ -z "$display_version" ]]; then # Fallback if NEW_VERSION wasn't set (e.g. published current without bump)
        display_version=$(node -p "require('$TS_CLIENT_DIR/package.json').version" 2>/dev/null || echo "latest")
      fi
      echo -e "${GREEN}✓${RESET} Successfully published ${BOLD}'$PACKAGE_NAME'@'$display_version'${RESET} to npm."
      echo -e "${YELLOW}  ↪ ${RESET}Verify on npm: ${CYAN}https://www.npmjs.com/package/$PACKAGE_NAME${RESET}"
    elif [[ "$VERSION_BUMPED" == true && -n "$NEW_VERSION" ]]; then # Bumped but not published
      echo -e "${YELLOW}⚠${RESET} Publishing to npm was skipped for ${BOLD}'$PACKAGE_NAME'@'$NEW_VERSION'${RESET}. To publish manually:"
      echo -e "    cd ${CYAN}$TS_CLIENT_DIR${RESET}"
      echo -e "    npm publish"
    elif [[ "$VERSION_BUMPED" != true && -z "$NEW_VERSION" && "${confirm_process,,}" == "y" ]]; then # Opted into versioning but skipped all steps (no bump, no publish attempt)
      log_info "No version bump or publish action was taken for '$PACKAGE_NAME'."
    fi
  fi

  # General guidance if no versioning/publishing was attempted or if user skipped the whole process
  # This covers:
  # 1. PACKAGE_NAME was not readable (early exit from handle_versioning_and_publishing)
  # 2. User answered "N" to the initial "Do you want to proceed..." prompt
  if [[ -z "$PACKAGE_NAME" || "${confirm_process,,}" != "y" ]]; then
    echo
    echo -e "${BOLD}${CYAN}Manual Versioning & Publishing (if needed):${RESET}"
    echo -e "${YELLOW}→${RESET} Navigate to: ${CYAN}$TS_CLIENT_DIR${RESET}"
    echo -e "${YELLOW}→${RESET} Review changes, then consider versioning using commands like:"
    echo -e "    ${CYAN}npm version patch|minor|major${RESET}"
    echo -e "    ${CYAN}npm version prerelease --preid=dev${RESET}"
    echo -e "${YELLOW}→${RESET} Then publish to npm:"
    echo -e "    ${CYAN}npm publish${RESET}"
  fi
  echo -e "${BOLD}${MAGENTA}============================================${RESET}"
  echo
}

# Main function
main() {
  # Parse command line arguments
  while [[ $# -gt 0 ]]; do
    case $1 in
    -h | --help)
      show_usage
      exit 0
      ;;
    -v | --verbose)
      set -x # Enable debug tracing
      shift
      ;;
    *)
      log_error "Unknown option: $1"
      show_usage
      exit 1
      ;;
    esac
  done

  # Display header
  echo -e "${BOLD}${MAGENTA}====================================${RESET}"
  echo -e "${BOLD}${MAGENTA}    OTR API Toolchain Runner    ${RESET}"
  echo -e "${BOLD}${MAGENTA}====================================${RESET}"
  echo

  # Execute pipeline
  validate_environment
  install_dependencies
  generate_swagger
  copy_swagger
  run_nswag
  build_typescript_client
  format_code

  # Optional versioning and publishing (interactive)
  handle_versioning_and_publishing

  show_completion_summary
}

# Only run main if script is executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
