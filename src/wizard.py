# SPDX-License-Identifier: AGPL-3.0-only
import queue,threading,tkinter as tk
from tkinter import ttk,filedialog,messagebox
from transport import Connection
from firmware import discover,inspect_image
from engine import state,guard,run_trial,stop_trial,save_configuration,app_folder

class SetupWindow:
    def __init__(self,root):
        self.root=root;self.events=queue.Queue();self.busy=False
        self.detected=None;self.evidence=None;self.profile=None;self.trial=None;self.confirmed=False
        root.title('CSL DD No-Rim Setup');root.geometry('900x730');root.minsize(840,680)
        root.configure(bg='#eef2f6')
        style=ttk.Style(root);style.theme_use('clam')
        style.configure('.',font=('Segoe UI',10))
        style.configure('TFrame',background='#eef2f6')
        style.configure('Card.TFrame',background='#ffffff')
        style.configure('TLabel',background='#eef2f6',foreground='#172b42')
        style.configure('Card.TLabel',background='#ffffff',foreground='#172b42')
        style.configure('Title.TLabel',font=('Segoe UI',21,'bold'))
        style.configure('Step.TLabel',font=('Segoe UI',12,'bold'),background='#ffffff')
        style.configure('TButton',padding=(12,7))
        style.configure('Primary.TButton',background='#126a74',foreground='white')
        style.map('Primary.TButton',background=[('disabled','#d9e1e8'),('active','#0c535c')],foreground=[('disabled','#7d8994')])
        style.configure('TCheckbutton',background='#ffffff',padding=(0,5))
        outer=ttk.Frame(root,padding=20);outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='CSL DD No-Rim Setup',style='Title.TLabel').pack(anchor='w')
        ttk.Label(outer,text='Check the firmware. Test your setup. Create a launcher.',font=('Segoe UI',11)).pack(anchor='w',pady=(4,12))
        card1=ttk.Frame(outer,style='Card.TFrame',padding=14);card1.pack(fill='x',pady=(0,10))
        ttk.Label(card1,text='1  Detect and check firmware',style='Step.TLabel').pack(anchor='w')
        self.base_text=tk.StringVar(value='Connect one CSL DD in yellow compatibility mode.')
        ttk.Label(card1,textvariable=self.base_text,style='Card.TLabel',wraplength=790).pack(anchor='w',pady=(8,5))
        self.evidence_text=tk.StringVar(value='Detection only reads status. It does not enable the motor.')
        ttk.Label(card1,textvariable=self.evidence_text,style='Card.TLabel',wraplength=790).pack(anchor='w',pady=(0,10))
        row=ttk.Frame(card1,style='Card.TFrame');row.pack(fill='x')
        self.detect_button=ttk.Button(row,text='Detect base',command=self.detect);self.detect_button.pack(side='left')
        self.image_button=ttk.Button(row,text='Inspect firmware image...',command=self.choose_image);self.image_button.pack(side='left',padx=8)
        card2=ttk.Frame(outer,style='Card.TFrame',padding=14);card2.pack(fill='x',pady=(0,10))
        ttk.Label(card2,text='2  Test the command',style='Step.TLabel').pack(anchor='w')
        self.test_text=tk.StringVar(value='The test becomes available after a reviewed firmware profile is found.')
        ttk.Label(card2,textvariable=self.test_text,style='Card.TLabel',wraplength=790).pack(anchor='w',pady=(8,5))
        self.clear=tk.BooleanVar(value=False)
        self.clear_check=ttk.Checkbutton(card2,text='The wheel is clear of hands and objects; games and FFB tests are closed.',variable=self.clear,command=self.update_controls)
        self.clear_check.pack(anchor='w')
        self.test_button=ttk.Button(card2,text='Test command and enable for game',style='Primary.TButton',command=self.test)
        self.test_button.pack(anchor='w',pady=(6,0))
        card3=ttk.Frame(outer,style='Card.TFrame',padding=14);card3.pack(fill='x',pady=(0,10))
        ttk.Label(card3,text='3  Confirm it in a game',style='Step.TLabel').pack(anchor='w')
        ttk.Label(card3,text='After the command test, try steering and low-strength FFB in your game.\nReturn here and confirm only if it worked.',style='Card.TLabel',wraplength=790).pack(anchor='w',pady=(8,10))
        row=ttk.Frame(card3,style='Card.TFrame');row.pack(fill='x')
        self.save_button=ttk.Button(row,text='It worked - create launcher',style='Primary.TButton',command=self.save);self.save_button.pack(side='left')
        self.stop_button=ttk.Button(row,text='Stop test / disable',command=self.stop);self.stop_button.pack(side='left',padx=8)
        self.message=tk.StringVar(value='Ready.')
        ttk.Label(outer,textvariable=self.message,wraplength=850,font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(3,8))
        ttk.Label(outer,text='The override resets when the base restarts. This app never flashes firmware.',wraplength=850,foreground='#5b6c7d').pack(anchor='w',side='bottom')
        root.protocol('WM_DELETE_WINDOW',self.close)
        self.update_controls();root.after(100,self.poll);root.after(200,self.detect)

    def update_controls(self):
        available=bool(self.profile and self.detected and self.detected['base_type']==10 and self.detected['rim_id']==0 and self.detected['status_profile']==7)
        active=bool(self.trial and not self.confirmed)
        def setting(button,enabled):button.configure(state='normal' if enabled else 'disabled')
        setting(self.detect_button,not self.busy and not active)
        setting(self.image_button,not self.busy and bool(self.detected) and not active)
        setting(self.clear_check,not self.busy and available and not active)
        setting(self.test_button,not self.busy and available and self.clear.get() and not active)
        setting(self.save_button,not self.busy and active)
        setting(self.stop_button,not self.busy and available)

    def async_run(self,fn,on_success):
        if self.busy:return
        self.busy=True;self.update_controls()
        def work():
            try:self.events.put(('done',on_success,fn()))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=work,daemon=False).start()

    def progress(self,text):self.events.put(('progress',text))

    def poll(self):
        try:
            while True:
                event=self.events.get_nowait()
                if event[0]=='progress':self.message.set(event[1])
                elif event[0]=='done':
                    self.busy=False;event[1](event[2]);self.update_controls()
                else:
                    self.busy=False;self.message.set(event[1]);self.update_controls()
                    messagebox.showerror('Operation did not complete',event[1],parent=self.root)
        except queue.Empty:pass
        try:
            if self.root.winfo_exists():self.root.after(100,self.poll)
        except tk.TclError:pass

    def detect(self):
        self.message.set('Reading the base and checking locally available firmware...')
        self.clear.set(False);self.trial=None;self.confirmed=False;self.profile=None
        self.base_text.set('Detecting the connected base...')
        self.evidence_text.set('Checking local firmware and reviewed profiles...')
        def work():
            s=state(Connection())
            if s['base_type']!=10:raise RuntimeError('The connected device is not identified as a CSL DD.')
            return s,discover(s['firmware'])
        def done(result):
            self.detected,self.evidence=result;self.show_evidence()
        self.async_run(work,done)

    def show_evidence(self):
        s=self.detected;self.profile=self.evidence.get('profile')
        self.base_text.set('CSL DD  |  Firmware '+s['firmware']+'  |  '+('No rim detected' if s['rim_id']==0 else 'Rim detected'))
        if not self.profile:
            self.evidence_text.set('Not verified: '+self.evidence['basis'])
            self.test_text.set('Unrecognized firmware stays blocked. A byte-pattern match alone does not authorize a test.')
            self.message.set('This image/version needs review before the command can be tested.')
        else:
            tested=' FFB has been confirmed on one CSL DD; you still need to test your own setup.' if self.profile.get('hardware_tested') else ''
            self.evidence_text.set('Command present in the reviewed firmware profile. '+self.evidence['basis']+tested)
            if self.profile['readback']=='availability15':
                self.test_text.set('The app will verify a reversible state change, then leave the override enabled for your game test.')
            else:
                self.test_text.set('This firmware does not report the override flag. The app can check command delivery, but only your game test can confirm FFB works.')
            self.message.set('Ready for your test. Nothing has been enabled by detection.')
            try:guard(s,self.profile)
            except RuntimeError as exc:self.message.set(str(exc))

    def choose_image(self):
        path=filedialog.askopenfilename(title='Choose a matching CSL DD firmware image',filetypes=[('Firmware images','*.hex *.bin'),('All files','*.*')],parent=self.root)
        if not path:return
        self.clear.set(False);self.profile=None;self.trial=None;self.confirmed=False
        self.evidence_text.set('Inspecting the selected image...')
        self.message.set('Inspecting the selected image without changing the base...')
        def done(evidence):self.evidence=evidence;self.show_evidence()
        self.async_run(lambda:inspect_image(path,self.detected['firmware']),done)

    def test(self):
        if not self.clear.get() or not self.profile:return
        self.message.set('Starting the user-requested test...')
        def done(record):
            self.trial=record;self.confirmed=False;self.clear.set(False)
            self.message.set('Game test ready. Try low-strength FFB, then confirm below. The override is left enabled.')
        self.async_run(lambda:run_trial(Connection(),self.profile,self.detected,self.progress),done)

    def save(self):
        if not self.trial:return
        self.message.set('Checking the setup and saving your confirmation...')
        def work():return save_configuration(app_folder(),self.trial,state(Connection()),True)
        def done(path):
            self.confirmed=True
            self.message.set('Saved. Double-click Enable.cmd in this folder after each base restart. You can close Setup now.')
            messagebox.showinfo('Launcher created','Your confirmed setup was saved.\n\nUse Enable.cmd in the same folder next time. Keep the whole folder together.\n\n'+str(path),parent=self.root)
        self.async_run(work,done)

    def stop(self,close_after=False):
        if not self.profile:return
        self.message.set('Disabling the override...')
        def done(text):
            self.trial=None;self.clear.set(False);self.message.set(text)
            if close_after:
                if self.profile['readback']=='manual':messagebox.showinfo('Disable command sent',text,parent=self.root)
                self.root.destroy()
        self.async_run(lambda:stop_trial(Connection(),self.profile,self.detected),done)

    def close(self):
        if self.busy:
            messagebox.showinfo('Operation in progress','Please wait for the current check or command to finish.',parent=self.root);return
        if self.trial and not self.confirmed:
            answer=messagebox.askyesnocancel('Game test active','Disable the override before closing?\n\nYes: send disable and close.\nNo: leave it enabled without saving a launcher.\nCancel: return to Setup.',parent=self.root)
            if answer is None:return
            if answer:self.stop(close_after=True);return
        self.root.destroy()

def main():
    root=tk.Tk();SetupWindow(root);root.mainloop()

def check_ui():
    """Verify GUI dependencies without displaying a window or running detection."""
    root=tk.Tk();root.withdraw()
    try:
        ui=SetupWindow(root);root.update_idletasks()
        return {'gui_initialized':True,'tcl':root.tk.call('info','patchlevel'),
                'test_disabled':str(ui.test_button['state'])=='disabled',
                'confirmation_disabled':str(ui.save_button['state'])=='disabled',
                'requested_size':[root.winfo_reqwidth(),root.winfo_reqheight()]}
    finally:root.destroy()

if __name__=='__main__':main()
