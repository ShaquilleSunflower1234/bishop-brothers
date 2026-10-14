import sys, os, json, hashlib, threading, queue
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
from core import Package, merge, sign_keyvault, require
from storage import discover, drives, put_back
ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
# Keep the existing data location so prior backups and recovery jobs remain accessible.
DATA=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'BishopMerge'
DONOR_HASH='8e6da0aba05eddad6e3203e64ea5ec62a1dc6689d6ca2e644031f2382f8648ad'
SIGNER_HASH='7c78be88ac35565ab688164efb195b49608377a281644e58773ac8d1271aa493'
VERSION='1.0.0'

def prepare(source,folder,key_path=''):
    original=source.read_bytes();package=Package(original);donors=(ROOT/'assets'/'bishops.bin').read_bytes()
    require(hashlib.sha256(donors).hexdigest()==DONOR_HASH,'Bishop assets are damaged.')
    payload,report=merge(package.payload,donors);package.replace(payload);data=bytes(package.data)
    key=Path(key_path) if key_path else ROOT/'assets/horizon-con-signing.bin'
    require(key.stat().st_size in (0x3ff0,0x4000),'Signing component is not supported.')
    signing_data=key.read_bytes()
    if not key_path:require(hashlib.sha256(signing_data).hexdigest()==SIGNER_HASH,'The built-in signing component is damaged.')
    data=sign_keyvault(package,signing_data,preserve_console_id=not bool(key_path))
    require(Package(data).payload==payload,'Signed boxer data failed verification.')
    dest=folder/('BishopBrothers-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'));dest.mkdir(parents=True)
    (dest/'Original backup').mkdir();backup=dest/'Original backup'/source.name;backup.write_bytes(original)
    require(backup.read_bytes()==original,'Backup verification failed.')
    output=dest/'Signed copy';output.mkdir()
    candidate=output/source.name;candidate.write_bytes(data)
    report.update(source=str(source),profile_id=original[0x371:0x379].hex().upper(),input_sha256=hashlib.sha256(original).hexdigest(),
        payload_sha256=hashlib.sha256(payload).hexdigest(),candidate=str(candidate),signing_status='verified',returned=False,hardware_test='pending')
    (dest/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (dest/'Instructions.txt').write_text('Original backup contains your untouched save.\nBishop Brothers signs and returns the save automatically. No Horizon or signing setup is required.\nAfter the app reports completion, safely eject USB. On Xbox 360, copy Fight Night Champion Boxers to Cloud Saved Games.\nOn Xbox One use the same account and allow syncing. Xbox gameplay testing of this merged output remains pending.\n',encoding='utf-8')
    return dest,report

def finish(dest):
    dest=Path(dest);report=json.loads((dest/'validation.json').read_text(encoding='utf-8'))
    require(not report.get('returned'),'This save was already put back.')
    source=Path(report['source']);candidate=Path(report['candidate'])
    require(candidate.resolve().is_relative_to(dest.resolve()),'Invalid prepared-copy location.')
    require(hashlib.sha256((dest/'Original backup'/source.name).read_bytes()).hexdigest()==report['input_sha256'],'Backup verification failed.')
    data=candidate.read_bytes();put_back(source,report['input_sha256'],data,report['payload_sha256'],report['profile_id'])
    report.update(returned=True,signing_status='verified',output_sha256=hashlib.sha256(data).hexdigest())
    (dest/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8');return report

class App:
    def __init__(self):
        self.config={}
        try:self.config=json.loads((DATA/'settings.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
        self.saves=[];self.busy=False;self.events=queue.Queue();self.window=TkinterDnD.Tk()
        self.window.drop_target_register(DND_FILES);self.window.dnd_bind('<<Drop>>',self.drop_folder)
        self.window.title(f'Bishop Brothers {VERSION} — Fight Night Champion');self.window.geometry('800x600');self.window.minsize(740,580);self.window.configure(bg='#101923')
        style=ttk.Style();style.theme_use('clam');style.configure('TFrame',background='#101923')
        style.configure('TLabel',background='#101923',foreground='#e4edf5',font=('Segoe UI',11));style.configure('Title.TLabel',font=('Segoe UI',26,'bold'))
        style.configure('Muted.TLabel',foreground='#a9bac9');style.configure('TButton',font=('Segoe UI',11),padding=10)
        frame=ttk.Frame(self.window,padding=28);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='BISHOP BROTHERS',style='Title.TLabel').pack(anchor='w')
        ttk.Label(frame,text='Plug in your Xbox 360 USB, or drop your Content folder here.',style='Muted.TLabel').pack(anchor='w',pady=(6,18))
        row=ttk.Frame(frame);row.pack(fill='x')
        self.scan_button=ttk.Button(row,text='Find my USB saves',command=self.scan);self.scan_button.pack(side='left')
        self.folder_button=ttk.Button(row,text='Use a copied folder',command=self.choose_folder);self.folder_button.pack(side='left',padx=10)
        ttk.Label(frame,text='Choose your profile and boxer save',style='Muted.TLabel').pack(anchor='w',pady=(18,6))
        self.list=tk.Listbox(frame,height=5,bg='#1b2b3b',fg='#e4edf5',selectbackground='#276b9f',font=('Segoe UI',11),exportselection=False)
        self.list.pack(fill='x');self.list.bind('<<ListboxSelect>>',lambda e:self.update_buttons())
        self.status=tk.StringVar(value='Looking for Fight Night Champion…');ttk.Label(frame,textvariable=self.status,wraplength=710).pack(anchor='w',pady=(14,8))
        self.add=ttk.Button(frame,text='Add Bishops',command=self.start_merge);self.add.pack(fill='x')
        self.finish_button=ttk.Button(frame,text='Resume interrupted update',command=self.finish_job);self.finish_button.pack(fill='x',pady=(8,0))
        row=ttk.Frame(frame);row.pack(fill='x',pady=(14,6))
        ttk.Button(row,text='Open backups',command=self.open_backups).pack(side='left')
        ttk.Button(row,text='Recovery options',command=self.settings).pack(side='left',padx=10)
        ttk.Label(frame,text=f'Version {VERSION} • Xbox success reported • Free to use',style='Muted.TLabel').pack(anchor='w')
        self.window.after(100,self.pump);self.window.after(200,lambda:self.scan(sys.argv[1] if len(sys.argv)>1 else None))
        self.update_buttons();self.window.mainloop()

    def save_config(self):
        DATA.mkdir(parents=True,exist_ok=True);(DATA/'settings.json').write_text(json.dumps(self.config,indent=2),encoding='utf-8')
    def update_buttons(self):
        self.add.state(['!disabled'] if self.list.curselection() and not self.busy else ['disabled'])
        self.finish_button.state(['!disabled'] if self.config.get('last_job') and not self.busy else ['disabled'])
        for button in (self.scan_button,self.folder_button):button.state(['disabled'] if self.busy else ['!disabled'])
    def run(self,operation,callback):
        if self.busy:return
        self.busy=True;self.update_buttons()
        def worker():
            try:self.events.put((callback,operation(),None))
            except Exception as error:self.events.put((callback,None,str(error)))
        threading.Thread(target=worker,daemon=True).start()
    def pump(self):
        try:
            while True:
                callback,result,error=self.events.get_nowait();self.busy=False
                if error:
                    self.status.set('Stopped before completion. Open backups to view any prepared copy.');messagebox.showerror('Could not complete this step',error)
                else:callback(result)
                self.update_buttons()
        except queue.Empty:pass
        self.window.after(100,self.pump)
    def choose_folder(self):
        folder=filedialog.askdirectory(title='Choose the USB drive, Content folder, or copied Xbox folder')
        if folder:self.scan(folder)
    def drop_folder(self,event):
        paths=self.window.tk.splitlist(event.data)
        if len(paths)==1:self.scan(paths[0])
        else:self.status.set('Drop one Xbox folder at a time so we can find its saves.')
        return 'copy'
    def scan(self,selected=None):
        if self.busy:return
        self.status.set('Finding Fight Night Champion inside the Xbox folders…')
        def operation():
            found=[];issues=[]
            for root in ([Path(selected)] if selected else drives()):
                items,errors=discover(root);found.extend(items);issues.extend(errors)
            return found,issues
        self.run(operation,self.show_saves)
    def show_saves(self,result):
        self.saves,issues=result;self.list.delete(0,'end')
        for save in self.saves:self.list.insert('end',save.label)
        if len(self.saves)==1:self.list.selection_set(0)
        self.status.set((f'Found {len(self.saves)} boxer save(s). Select yours and click Add Bishops. Backup, merge, signing and placement are automatic.') if self.saves else
            'No supported boxer saves found. Plug in the USB and rescan, or choose your copied Xbox folder.'+(' A game file failed validation.' if issues else ''))
        self.update_buttons()
    def start_merge(self):
        choice=self.list.curselection()
        if not choice:return
        if self.config.get('last_job'):
            messagebox.showinfo('Update waiting','Use Resume interrupted update or Recovery options to handle the prepared save first.');return
        save=self.saves[choice[0]]
        self.status.set('Backing up your save, adding the Bishops and signing…');self.run(lambda:prepare(save.path,DATA/'Exports'),self.prepared)
    def prepared(self,result):
        dest,report=result;self.config['last_job']=str(dest);self.save_config()
        if report['signing_status']=='verified':self.finish_job()
        else:
            self.status.set('An older prepared copy needs to be signed before it can be returned. Use Recovery options to start a fresh automatic update.')
    def finish_job(self):
        dest=self.config.get('last_job')
        if not dest:return
        self.status.set('Checking the signed copy and returning it to the Xbox folder…');self.run(lambda:finish(dest),self.completed)
    def completed(self,report):
        self.config.pop('last_job',None);self.save_config()
        self.status.set('Done. Backup verified; both Bishops are in the signed save, returned to the correct folder. Safely eject USB, then copy Fight Night Champion Boxers to Xbox 360 cloud storage.')
    def settings(self):
        window=tk.Toplevel(self.window);window.title('Recovery options');window.geometry('610x240');frame=ttk.Frame(window,padding=20);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='Signing is built in. No separate files or Horizon are needed.\nIf an older update is pending, you can start fresh and keep its backup.',wraplength=550).pack(anchor='w',pady=(0,16))
        def reset():
            self.config.pop('last_job',None);self.save_config();self.update_buttons();window.destroy()
        ttk.Button(frame,text='Start fresh (keep all backups)',command=reset).pack(anchor='w',pady=8)
        ttk.Label(frame,text='Backups are kept even if you clear an unfinished update.',wraplength=550).pack(anchor='w',pady=12)
    def open_backups(self):
        folder=Path(self.config['last_job']) if self.config.get('last_job') else DATA/'Exports';folder.mkdir(parents=True,exist_ok=True);os.startfile(folder)
if __name__=='__main__':App()
