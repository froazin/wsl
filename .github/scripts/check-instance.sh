#!/usr/bin/env sh
#
# Checks what the user-data set up in an instance after its first boot. Runs
# as root inside the instance.
#
# Usage: check-instance.sh [username [git-name]]
#
# Without arguments, it reads them from E2E_USER and E2E_GIT_NAME. Leave the
# username empty for an instance whose meta-data has none.

set -u

user="${1:-${E2E_USER:-}}"
git_name="${2:-${E2E_GIT_NAME:-}}"
failed="false"

# Runs a check and reports it. The first argument says what passing means.
check()
{
    _what="$1"
    shift

    if "$@" > /dev/null 2>&1; then
        printf 'ok    %s\n' "$_what"
    else
        printf '::error title=Instance check::%s\n' "$_what"
        failed="true"
    fi
}

links_to()
{
    [ "$(readlink "$1")" = "$2" ]
}

links_into_windows()
{
    case "$(readlink "$1")" in
        /mnt/c/*) return 0 ;;
        *) return 1 ;;
    esac
}

login_shell_is()
{
    [ "$(getent passwd "$1" | cut -d: -f7)" = "$2" ]
}

swap_is_off()
{
    [ -z "$(swapon --show --noheadings)" ]
}

root_is_shared()
{
    findmnt -no PROPAGATION / | grep -q shared
}

gh_is_from_cli_github()
{
    apt-cache policy gh | grep -A1 '^ \*\*\*' | grep -q cli.github.com
}

network_autostarts()
{
    virsh --connect qemu:///system net-info default | grep -Eq '^Autostart: +yes'
}

in_group()
{
    id -nG "$1" | tr ' ' '\n' | grep -qx "$2"
}

has_uid()
{
    [ "$(id -u "$1")" = "$2" ]
}

no_uid()
{
    ! getent passwd "$1"
}

git_config_is()
{
    [ "$(runuser -u "$1" -- git config --global --get "$2")" = "$3" ]
}

gh_is_git_credential_helper()
{
    runuser -u "$1" -- git config --global --get-all credential.https://github.com.helper \
        | grep -q 'gh auth git-credential'
}

if [ "$(id -u)" -ne 0 ]; then
    printf 'check-instance.sh must run as root\n' >&2
    exit 2
fi

# System config from write_files
check "wsl.conf turns systemd on" grep -qx 'systemd=true' /etc/wsl.conf
check "wsl.conf keeps the Windows PATH out" grep -qx 'appendWindowsPath=false' /etc/wsl.conf
check "gh is pinned to cli.github.com" grep -qx 'Pin: origin cli.github.com' /etc/apt/preferences.d/github-cli
check "BROWSER is set for login shells" grep -q 'BROWSER=/usr/local/bin/start' /etc/profile.d/browser.sh
check "/usr/local/bin/start is executable" test -x /usr/local/bin/start
check "the locale is en_GB.UTF-8" grep -q 'LANG=en_GB.UTF-8' /etc/default/locale

# Packages, the GitHub CLI source and the links runcmd makes
for cmd in zsh git gh jq curl direnv fzf python3 shellcheck shfmt podman buildah skopeo btop tree rg nmap virsh qemu-system-x86_64; do
    check "$cmd is installed" command -v "$cmd"
done

check "gh comes from cli.github.com" gh_is_from_cli_github
check "fd links to fdfind" links_to /usr/local/bin/fd /usr/bin/fdfind
check "fd runs" /usr/local/bin/fd --version

for tool in code op ssh ssh-add clip; do
    check "/usr/local/bin/$tool links into Windows" links_into_windows "/usr/local/bin/$tool"
done

# systemd units
check "swap is off" swap_is_off
check "/ is a shared mount" root_is_shared
check "disable-swap.service is enabled" systemctl is-enabled disable-swap.service
check "make-root-rshared.service is enabled" systemctl is-enabled make-root-rshared.service
check "root's podman.socket is active" systemctl is-active podman.socket
check "podman.socket is enabled for users" systemctl --global is-enabled podman.socket
check "libvirt's default network autostarts" network_autostarts

# Root's shell and dotfiles
check "root's login shell is zsh" login_shell_is root /usr/bin/zsh
check "new users get zsh" grep -qx 'DSHELL=/usr/bin/zsh' /etc/adduser.conf
check "the dotfiles are installed for root" test -e /root/.zshrc

if [ -z "$user" ]; then
    check "no user with uid 1000 exists" no_uid 1000
else
    home="/home/$user"

    check "$user has uid 1000" has_uid "$user" 1000
    check "$user's login shell is zsh" login_shell_is "$user" /usr/bin/zsh
    for group in sudo kvm libvirt users; do
        check "$user is in $group" in_group "$user" "$group"
    done
    check "$user has passwordless sudo" runuser -u "$user" -- sudo -n true

    if [ -n "$git_name" ]; then
        check "git reads user.name back for $user" git_config_is "$user" user.name "$git_name"
    fi
    check "git uses gh for github.com" gh_is_git_credential_helper "$user"

    check "$user's workspaces exist" test -d "$home/workspaces"
    check "the dotfiles are cloned for $user" test -d "$home/workspaces/github.com/froazin/dotfiles/.git"
    check "the dotfiles are installed for $user" test -e "$home/.zshrc"

    for tool in .local/bin/uv .local/bin/claude .local/bin/ant .local/bin/biome .pulumi/bin/pulumi; do
        check "$user has ~/$tool" test -x "$home/$tool"
    done
    check "$user has nvm" test -s "$home/.nvm/nvm.sh"
    check "$user has the gh act extension" test -d "$home/.local/share/gh/extensions/gh-act"
fi

if [ "$failed" = "true" ]; then
    exit 1
fi

printf 'Every check passed.\n'
