"""The main vault screen: a filterable list of entry names and a detail pane."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static

from lwpm import crypto
from lwpm.screens.confirm import ConfirmModal
from lwpm.screens.entry_modal import EntryModal

MASK = "•" * 8  # ••••••••


class VaultScreen(Screen):
    """Lists credential names and shows the selected entry's details."""

    BINDINGS = [
        ("a", "add", "Add"),
        ("e", "edit", "Edit"),
        ("d", "delete", "Delete"),
        ("c", "copy_password", "Copy pw"),
        ("u", "copy_username", "Copy user"),
        ("p", "change_password", "Master pw"),
        ("slash", "search", "Search"),
        ("l", "lock", "Lock"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal():
            with Vertical(id="left"):
                yield Input(id="search", placeholder="search…")
                yield ListView(id="names")
            yield Static(id="detail")
        yield Footer()

    def on_mount(self) -> None:
        self._names: list[str] = []
        self._pre_search_selected_name: str | None = None
        self.query_one("#search", Input).display = False
        self.refresh_list(select=getattr(self.app, "last_selected_name", None))
        self.query_one("#names", ListView).focus()

    # -- list management ------------------------------------------------

    def refresh_list(self, select: str | None = None) -> None:
        search = self.query_one("#search", Input)
        query = search.value if search.display else ""
        self._names = self.app.vault.search_names(query)

        names = self.query_one("#names", ListView)
        names.clear()
        for name in self._names:
            names.append(ListItem(Label(name)))

        if self._names:
            index = self._names.index(select) if select in self._names else 0
            names.index = index
            self.app.last_selected_name = self._names[index]
            self._show_detail(self._names[index])
        else:
            self.app.last_selected_name = None
            self._render_empty()

    @property
    def selected_name(self) -> str | None:
        names = self.query_one("#names", ListView)
        if names.index is None or not self._names:
            return None
        return self._names[names.index]

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if self.selected_name is not None:
            self.app.last_selected_name = self.selected_name
            self._show_detail(self.selected_name)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search" and event.input.display:
            self.refresh_list()

    # -- detail rendering -----------------------------------------------

    def _decrypt(self, name: str) -> dict:
        blob = self.app.vault.get_secret_blob(name)
        return crypto.decrypt_fields(self.app.key, blob)

    def _show_detail(self, name: str) -> None:
        fields = self._decrypt(name)
        lines = [
            f"[b]{name}[/b]",
            "",
            f"Username: {fields.get('username', '')}",
            f"URL:      {fields.get('url', '')}",
            f"Password: {MASK}",
            "",
            "Notes:",
            fields.get("notes", ""),
        ]
        self.query_one("#detail", Static).update("\n".join(lines))

    def _render_empty(self) -> None:
        self.query_one("#detail", Static).update("No entries yet. Press 'a' to add one.")

    # -- actions --------------------------------------------------------

    def action_add(self) -> None:
        def after(saved: bool) -> None:
            if saved:
                self.refresh_list()

        self.app.push_screen(EntryModal(), after)

    def action_edit(self) -> None:
        name = self.selected_name
        if name is None:
            return
        fields = self._decrypt(name)

        def after(saved: bool) -> None:
            if saved:
                self.refresh_list(select=name)

        self.app.push_screen(EntryModal(name=name, fields=fields), after)

    def action_delete(self) -> None:
        name = self.selected_name
        if name is None:
            return

        def after(confirmed: bool) -> None:
            if confirmed:
                self.app.vault.delete_credential(name)
                self.refresh_list()

        self.app.push_screen(ConfirmModal(f"Delete entry '{name}'?"), after)

    def action_copy_password(self) -> None:
        name = self.selected_name
        if name is None:
            return
        fields = self._decrypt(name)
        self.app.copy_to_clipboard_value(fields["password"], "Password")

    def action_copy_username(self) -> None:
        name = self.selected_name
        if name is None:
            return
        username = self._decrypt(name).get("username")
        if username:
            self.app.copy_to_clipboard_value(username, "Username")
        else:
            self.notify("No username for this entry.", severity="warning")

    def action_change_password(self) -> None:
        from lwpm.screens.change_password_modal import ChangePasswordModal

        self.app.push_screen(ChangePasswordModal())

    def action_search(self) -> None:
        search = self.query_one("#search", Input)
        search.display = not search.display
        if search.display:
            self._pre_search_selected_name = (
                self.selected_name or getattr(self.app, "last_selected_name", None)
            )
            search.focus()
        else:
            pre_search = self._pre_search_selected_name
            self._pre_search_selected_name = None
            search.value = ""
            self.refresh_list(select=pre_search)
            self.query_one("#names", ListView).focus()

    def action_lock(self) -> None:
        self.app.lock()

    def action_quit(self) -> None:
        self.app.exit()
