"""Protect the loaded profile's appearance buffer while changing processes.

The combo is rolled back before presenting a choice, so Save always targets
its original loaded file. Session identities, not combo indices, survive polls.
"""

from pathlib import Path

from . import mangohud


def profile_name(path, global_path):
    path, global_path = Path(path).absolute(), Path(global_path).absolute()
    if path == global_path:
        return "Global configuration"
    name = path.stem
    return name[5:] if name.startswith("wine-") else name


def find_identity(combo, identity):
    # QVariant's PyObject comparison can use tuple object identity. Polls create
    # new tuples, so compare the stable (pid, start-time) values in Python.
    return next((i for i in range(combo.count()) if combo.itemData(i) == identity), -1)


class ProfileSwitch:
    def __init__(self, window):
        self.window = window
        self.identity = None
        self.baseline = None
        self.source = None
        self.pending = None

    def values(self):
        values = self.window.customization_values()
        values.update(
            {key: int(field.isChecked()) for key, field in self.window.metric_controls.items()}
        )
        return values

    def accepted(self, path):
        self.identity = self.window.process.currentData()
        self.source = Path(path).absolute()
        self.baseline = self.values()

    def restore_selection(self):
        combo = self.window.process
        index = find_identity(combo, self.identity) if self.identity is not None else -1
        combo.blockSignals(True)
        combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def request(self):
        window = self.window
        target = window.process.currentData()
        if self.pending is not None:
            self.restore_selection()
            return False
        if target == self.identity or self.baseline is None or self.values() == self.baseline:
            return True
        self.restore_selection()
        if window.status.actions is not None:
            window.status.hide_immediately(force=True)
        self.pending = (target, self.source)
        name = profile_name(self.source, Path(window.config_path.text()).expanduser())
        destination = next(
            (session.name for session in window.sessions if session.identity == target),
            "Global configuration",
        )
        window.status.show_options(
            "Unsaved changes",
            f"{name} has unsaved appearance changes. Switch to {destination}?",
            (
                (
                    "Save and switch",
                    "Save the current profile before switching",
                    self.source,
                    lambda: self.resolve(True),
                    True,
                ),
                (
                    "Discard and switch",
                    "Switch without saving these changes",
                    None,
                    lambda: self.resolve(False),
                    False,
                ),
            ),
            window.status.dismiss,
        )
        window.message_until = 0
        window.update_configuration_button()
        return False

    def resolve(self, save):
        if self.pending is None:
            return
        window = self.window
        target, source = self.pending
        index = find_identity(window.process, target) if target is not None else -1
        if target is not None and index < 0:
            window.status.choice_error(
                "The selected application has exited. Cancel to keep editing."
            )
            return
        if save:
            try:
                if source.is_symlink():
                    raise mangohud.ControlError(
                        "The profile is a symlink; the shared file will not be changed."
                    )
                global_path = Path(window.config_path.text()).expanduser().absolute()
                mangohud.save_appearance(source, self.values(), template=global_path)
                self.baseline = self.values()
            except (OSError, ValueError, UnicodeError, mangohud.ControlError) as error:
                window.status.choice_error("Cannot save: " + str(error))
                return
        self.pending = None
        window.status.hide_immediately(force=True)
        window.process.blockSignals(True)
        window.process.setCurrentIndex(index)
        window.process.blockSignals(False)
        window.selection_changed(force=True)

    def cancelled(self):
        if self.pending is not None:
            self.pending = None
            self.restore_selection()
