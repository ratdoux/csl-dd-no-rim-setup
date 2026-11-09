# SPDX-License-Identifier: AGPL-3.0-only
"""A guided setup and daily-use window. Detection never enables force feedback."""
from pathlib import Path
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from desktop import create_desktop_shortcut
from engine import (app_folder, binding, enable_saved, guard, load_configuration,
                    run_trial, save_configuration, state, stop_trial)
from firmware import discover, inspect_image
from transport import Connection
from version import APP_VERSION


class SetupWindow:
    def __init__(self, root, *, folder=None, auto_detect=True):
        self.root = root
        self.folder = Path(folder) if folder is not None else app_folder()
        self.events = queue.Queue()
        self.busy = False
        self.detected = self.evidence = self.profile = self.trial = None
        self.saved_config = None
        self.saved_matches = self.can_enable = False
        self.details_visible = False
        self._wrap_labels = []
        root.title('CSL DD No-Rim Setup')
        root.geometry('900x760')
        root.minsize(800, 640)
        root.configure(bg='#f1f4f7')
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10))
        style.configure('TFrame', background='#f1f4f7')
        style.configure('Card.TFrame', background='white')
        style.configure('TLabel', background='#f1f4f7', foreground='#1b2e42')
        style.configure('Card.TLabel', background='white', foreground='#1b2e42')
        style.configure('Muted.TLabel', background='white', foreground='#52667a')
        style.configure('Heading.TLabel', background='white', font=('Segoe UI', 12, 'bold'))
        style.configure('TButton', padding=(13, 8), background='#e8edf2', foreground='#1b2e42')
        style.configure('Primary.TButton', background='#087f8c', foreground='white', font=('Segoe UI', 10, 'bold'))
        style.map('Primary.TButton', background=[('disabled', '#dce5ea'), ('active', '#066672')],
                  foreground=[('disabled', '#7b8c97')])
        style.configure('TCheckbutton', background='white', padding=(0, 6))
        style.configure('Quiet.TButton', padding=(8, 5), background='#f1f4f7')

        shell = ttk.Frame(root, padding=(22, 18, 16, 14))
        shell.pack(fill='both', expand=True)
        header = ttk.Frame(shell)
        header.pack(fill='x', pady=(0, 14))
        ttk.Label(header, text='CSL DD No-Rim', font=('Segoe UI', 23, 'bold')).pack(anchor='w')
        ttk.Label(header, text='Enable force feedback with a passive or undetected rim.',
                  font=('Segoe UI', 11)).pack(anchor='w', pady=(3, 0))
        ttk.Label(header, text='Setup ' + APP_VERSION, foreground='#687c8e').place(relx=1, x=-8, y=8, anchor='ne')

        area = ttk.Frame(shell)
        area.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(area, bg='#f1f4f7', highlightthickness=0)
        scrollbar = ttk.Scrollbar(area, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.content = ttk.Frame(self.canvas)
        self.content_window = self.canvas.create_window((0, 0), window=self.content, anchor='nw')
        self.content.bind('<Configure>', lambda event: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', self.resize)
        root.bind('<MouseWheel>', self.scroll)

        first = self.card('1  Check your wheelbase')
        self.status_title = tk.StringVar(value='Checking your connection...')
        self.status_label = tk.Label(first, textvariable=self.status_title, bg='white', fg='#087f8c',
                                     font=('Segoe UI', 15, 'bold'), anchor='w')
        self.status_label.pack(fill='x', pady=(8, 2))
        self.device_text = tk.StringVar(value='Connect one CSL DD by USB and select yellow PC compatibility mode.')
        self.label(first, self.device_text)
        self.connection_text = tk.StringVar(value='The app checks the base and firmware automatically. No command is sent by detection.')
        self.label(first, self.connection_text, muted=True, pady=(3, 10))
        self.detect_button = ttk.Button(first, text='Check again', command=self.detect)
        self.detect_button.pack(anchor='w')

        second = self.card('2  Enable force feedback')
        self.enable_help = tk.StringVar(value='Once the checks pass, use the button below before starting your game.')
        self.label(second, self.enable_help, pady=(8, 4))
        self.clear = tk.BooleanVar(value=False)
        self.clear_check = ttk.Checkbutton(second, text='The wheel is clear; games and other FFB tests are closed.',
                                          variable=self.clear, command=self.update_controls)
        self.clear_check.pack(anchor='w')
        row = ttk.Frame(second, style='Card.TFrame')
        row.pack(fill='x', pady=(4, 0))
        self.test_button = ttk.Button(row, text='Enable FFB', style='Primary.TButton', command=self.enable)
        self.test_button.pack(side='left')
        self.stop_button = ttk.Button(row, text='Disable', command=self.stop)
        self.stop_button.pack(side='left', padx=(8, 0))

        third = self.card('3  Save for next time')
        self.saved_text = tk.StringVar(value='First enable FFB and try it in a game. Then confirm below to save your setup.')
        self.label(third, self.saved_text, pady=(8, 10))
        row = ttk.Frame(third, style='Card.TFrame')
        row.pack(fill='x')
        self.save_button = ttk.Button(row, text='FFB works - save setup', command=self.save)
        self.save_button.pack(side='left')
        self.shortcut_button = ttk.Button(row, text='Add desktop shortcut', command=self.add_shortcut)
        self.shortcut_button.pack(side='left', padx=(8, 0))
        self.shortcut_text = tk.StringVar(value='The shortcut runs Enable.cmd. Keep the app folder in its current location.')
        self.label(third, self.shortcut_text, muted=True, pady=(9, 0))

        self.details_button = ttk.Button(self.content, text='Show technical details', style='Quiet.TButton', command=self.toggle_details)
        self.details_button.pack(anchor='w', pady=(0, 7))
        self.details_frame = ttk.Frame(self.content, style='Card.TFrame', padding=14)
        self.details_text = tk.StringVar(value='Firmware inspection details will appear after detection.')
        self.label(self.details_frame, self.details_text, muted=True, pady=(0, 8))
        self.image_button = ttk.Button(self.details_frame, text='Inspect a firmware image...', command=self.choose_image)
        self.image_button.pack(anchor='w')

        footer = ttk.Frame(shell)
        footer.pack(fill='x', pady=(10, 0))
        self.message = tk.StringVar(value='Checking the connected wheelbase...')
        self.message_label = ttk.Label(footer, textvariable=self.message, wraplength=740, font=('Segoe UI', 10, 'bold'))
        self.message_label.pack(anchor='w')
        footer.bind('<Configure>', lambda event: self.message_label.configure(wraplength=max(300, event.width - 8)))
        row = ttk.Frame(footer)
        row.pack(fill='x', pady=(6, 0))
        ttk.Label(row, text='Re-enable after restarting the base. No firmware flashing.', foreground='#687c8e').pack(side='left')
        ttk.Button(row, text='Open app folder', style='Quiet.TButton', command=self.open_folder).pack(side='right')
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.load_saved()
        self.update_controls()
        root.after(100, self.poll)
        if auto_detect:
            root.after(200, self.detect)

    def card(self, title):
        frame = ttk.Frame(self.content, style='Card.TFrame', padding=16)
        frame.pack(fill='x', pady=(0, 12))
        ttk.Label(frame, text=title, style='Heading.TLabel').pack(anchor='w')
        return frame

    def label(self, parent, variable, *, muted=False, pady=0):
        label = ttk.Label(parent, textvariable=variable, style='Muted.TLabel' if muted else 'Card.TLabel',
                          wraplength=780, justify='left')
        label.pack(anchor='w', fill='x', pady=pady)
        self._wrap_labels.append(label)
        return label

    def resize(self, event):
        self.canvas.itemconfigure(self.content_window, width=event.width)
        for label in self._wrap_labels:
            label.configure(wraplength=max(300, event.width - 40))

    def scroll(self, event):
        if self.canvas.yview() != (0.0, 1.0):
            steps = max(1, abs(event.delta) // 120)
            self.canvas.yview_scroll(-steps if event.delta > 0 else steps, 'units')

    def set_status(self, title, kind='ready'):
        self.status_title.set(title)
        self.status_label.configure(fg={'ready': '#087f8c', 'working': '#48647c', 'attention': '#9c5410'}[kind])

    def load_saved(self):
        self.saved_config = None
        self.saved_matches = False
        try:
            self.saved_config, _ = load_configuration(self.folder)
            self.saved_text.set('Your setup for firmware ' + self.saved_config['binding']['firmware'] +
                                ' is saved. You can add a desktop shortcut below.')
        except (OSError, ValueError, RuntimeError, KeyError, TypeError):
            if (self.folder / 'setup-profile.json').exists():
                self.saved_text.set('Your previous setup needs confirmation again. Enable FFB and test it in a game first.')

    def update_controls(self):
        active = bool(self.trial)
        def setting(widget, enabled):
            widget.configure(state='normal' if enabled else 'disabled')
        setting(self.detect_button, not self.busy and not active)
        setting(self.image_button, not self.busy and bool(self.detected) and not active)
        setting(self.clear_check, not self.busy and self.can_enable and not active)
        setting(self.test_button, not self.busy and self.can_enable and self.clear.get() and not active)
        setting(self.stop_button, not self.busy and self.can_enable)
        setting(self.save_button, not self.busy and active)
        portable = (self.folder / 'Enable.cmd').is_file() and (self.folder / 'CSL-DD-No-Rim.exe').is_file()
        setting(self.shortcut_button, not self.busy and not active and bool(self.saved_config) and portable)

    def async_run(self, work, done, failed=None):
        if self.busy:
            return
        self.busy = True
        self.update_controls()
        def worker():
            try:
                self.events.put((True, done, work()))
            except Exception as exc:
                self.events.put((False, failed, str(exc)))
        threading.Thread(target=worker, daemon=False).start()

    def poll(self):
        try:
            while True:
                success, callback, result = self.events.get_nowait()
                self.busy = False
                if callback:
                    callback(result)
                    if not self.root.winfo_exists():
                        return
                elif not success:
                    self.clear.set(False)
                    self.set_status('Action did not complete', 'attention')
                    self.message.set(result)
                self.update_controls()
        except (queue.Empty, tk.TclError):
            pass
        try:
            if self.root.winfo_exists():
                self.root.after(100, self.poll)
        except tk.TclError:
            pass  # A completed disable-and-close action destroyed the window.

    def detect(self):
        if self.busy or self.trial:
            return
        self.can_enable = self.saved_matches = False
        self.detected = self.evidence = self.profile = None
        self.clear.set(False)
        self.set_status('Checking your connection...', 'working')
        self.message.set('Reading the base and checking its firmware...')
        self.connection_text.set('Checking the connected device. Detection does not enable FFB.')
        def work():
            detected = state(Connection())
            if detected['base_type'] != 10:
                raise RuntimeError('This app supports the CSL DD only.')
            return detected, discover(detected['firmware'])
        self.async_run(work, self.accept_detection, self.detection_failed)

    def detection_failed(self, message):
        self.can_enable = self.saved_matches = False
        self.detected = self.evidence = self.profile = None
        self.set_status('Check the connection', 'attention')
        self.device_text.set('Connect one CSL DD by USB and select yellow PC compatibility mode.')
        self.connection_text.set(message)
        self.message.set('After checking USB, power and PC mode, click Check again.')
        self.update_controls()

    def accept_detection(self, result):
        self.detected, self.evidence = result
        self.show_evidence()

    def show_evidence(self):
        current = self.detected
        self.profile = self.evidence.get('profile')
        self.can_enable = self.saved_matches = False
        self.device_text.set('CSL DD  |  Firmware ' + current['firmware'] + '  |  ' +
                             ('No rim detected (expected)' if current['rim_id'] == 0 else 'Rim detected'))
        self.details_text.set(self.evidence['basis'] +
                              ('\n\n' + self.profile['readback_note'] if self.profile else ''))
        try:
            guard(current, self.profile)
        except RuntimeError as exc:
            self.set_status('This setup needs attention', 'attention')
            self.connection_text.set(str(exc))
            self.enable_help.set('Enable is unavailable until the connected setup passes the checks.')
            self.message.set('No enable command has been sent.')
        else:
            self.can_enable = True
            self.saved_matches = bool(self.saved_config and binding(current) == self.saved_config['binding'])
            self.set_status('Ready to enable')
            self.connection_text.set('Firmware checks passed. ' +
                                     ('Your saved setup matches this base.' if self.saved_matches else 'This base is ready for your first game test.'))
            self.enable_help.set('Close your game, keep the wheel clear, then click Enable FFB.' +
                                 (' This firmware needs a game test to confirm force output.'
                                  if self.profile['readback'] == 'manual' and not self.saved_matches else ''))
            if not self.saved_matches:
                self.saved_text.set('After enabling, try FFB in a game. Return here and confirm only if it works.')
            self.message.set('Check the readiness box when you are ready. Detection has not enabled FFB.')
        self.update_controls()

    def enable(self):
        if self.busy or self.trial or not self.can_enable or not self.clear.get():
            return
        self.message.set('Sending the enable command...')
        self.set_status('Enabling force feedback...', 'working')
        if self.saved_matches:
            def done(message):
                self.clear.set(False)
                self.set_status('Command sent' if self.profile['readback'] == 'manual' else 'Override enabled')
                self.message.set(message + ' You can start your game.')
            self.async_run(lambda: enable_saved(Connection(), self.folder), done)
        else:
            def done(trial):
                self.trial = trial
                self.clear.set(False)
                self.set_status('Ready for your game test')
                self.message.set('Command sent. Try low-strength FFB in a game, then confirm below.')
                self.saved_text.set('If steering and FFB work in your game, click FFB works - save setup.')
            self.async_run(lambda: run_trial(Connection(), self.profile, self.detected), done)

    def save(self):
        if self.busy or not self.trial:
            return
        self.message.set('Checking the base and saving your confirmation...')
        def work():
            return save_configuration(self.folder, self.trial, state(Connection()), True)
        def done(path):
            self.trial = None
            self.load_saved()
            self.saved_matches = True
            self.set_status('Setup saved')
            self.message.set('Saved. Add a desktop shortcut for quick enabling next time.')
        self.async_run(work, done)

    def add_shortcut(self):
        if self.busy or self.trial or not self.saved_config:
            return
        self.message.set('Creating your desktop shortcut...')
        def done(path):
            self.shortcut_text.set('Desktop shortcut: ' + path.name + '\nKeep this app folder in place so the shortcut can find it.')
            self.message.set('Desktop shortcut ready. Use it before starting your game.')
        self.async_run(lambda: create_desktop_shortcut(self.folder), done)

    def stop(self, close_after=False):
        if self.busy or not self.can_enable:
            return
        self.message.set('Sending the disable command...')
        def done(message):
            self.trial = None
            self.clear.set(False)
            self.set_status('Disable command sent' if self.profile['readback'] == 'manual' else 'Override disabled')
            self.message.set(message)
            if not self.saved_config:
                self.saved_text.set('Enable again and confirm FFB in a game before saving your setup.')
            if close_after:
                self.root.destroy()
        self.async_run(lambda: stop_trial(Connection(), self.profile, self.detected), done)

    def toggle_details(self):
        self.details_visible = not self.details_visible
        if self.details_visible:
            self.details_frame.pack(fill='x', pady=(0, 10))
        else:
            self.details_frame.pack_forget()
        self.details_button.configure(text='Hide technical details' if self.details_visible else 'Show technical details')

    def choose_image(self):
        if self.busy or self.trial or not self.detected:
            return
        path = filedialog.askopenfilename(parent=self.root, title='Choose matching CSL DD firmware',
                                          filetypes=[('Firmware image', '*.hex'), ('All files', '*.*')])
        if not path:
            return
        self.clear.set(False)
        self.can_enable = self.saved_matches = False
        self.profile = None
        self.message.set('Inspecting the image without changing the base...')
        def done(evidence):
            self.evidence = evidence
            self.show_evidence()
        self.async_run(lambda: inspect_image(path, self.detected['firmware']), done)

    def open_folder(self):
        try:
            os.startfile(self.folder)
        except OSError as exc:
            self.message.set('Could not open the app folder: ' + str(exc))

    def close(self):
        if self.busy:
            messagebox.showinfo('Please wait', 'Let the current check or command finish before closing.', parent=self.root)
            return
        if self.trial:
            answer = messagebox.askyesnocancel('Game test is active',
                'Send the disable command before closing?\n\nYes: disable and close.\nNo: leave it enabled without saving.\nCancel: keep this window open.', parent=self.root)
            if answer is None:
                return
            if answer:
                self.stop(close_after=True)
                return
        self.root.destroy()


def main():
    root = tk.Tk()
    SetupWindow(root)
    root.mainloop()


def check_ui():
    """Initialize the packaged GUI without detection, device access or shortcuts."""
    root = tk.Tk()
    root.withdraw()
    try:
        ui = SetupWindow(root, auto_detect=False)
        root.update_idletasks()
        return {'gui_initialized': True, 'tcl': root.tk.call('info', 'patchlevel'),
                'test_disabled': str(ui.test_button['state']) == 'disabled',
                'confirmation_disabled': str(ui.save_button['state']) == 'disabled',
                'shortcut_button_present': bool(ui.shortcut_button.winfo_exists()),
                'requested_size': [root.winfo_reqwidth(), root.winfo_reqheight()]}
    finally:
        root.destroy()


if __name__ == '__main__':
    main()
