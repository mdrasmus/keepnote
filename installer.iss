[Setup]
AppName=KeepNote
AppVerName=KeepNote 0.4.6
AppPublisher=Matt Rasmussen
AppPublisherURL=http://rasm.ods.org/keepnote
DefaultDirName={pf}\KeepNote
DefaultGroupName=KeepNote
DisableProgramGroupPage=true
OutputBaseFilename=keepnote-0.4.6
Compression=lzma
SolidCompression=true
AllowUNCPath=false
VersionInfoVersion=0.4.6
VersionInfoCompany=Matt Rasmussen
VersionInfoDescription=KeepNote
ChangesAssociations=yes
OutputDir=dist\
;WizardImageFile=keepnote\images\keepnote-64x64.bmp
;WizardImageStretch=no
; PrivilegeRequired=admin

[Dirs]
Name: {app}; Flags: uninsalwaysuninstall;

[Files]
Source: dist\keepnote-0.4.6.win\*; DestDir: {app}; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: {group}\KeepNote; Filename: {app}\keepnote.exe; WorkingDir: {app}

[Run]
Filename: {app}\keepnote.exe; Description: {cm:LaunchProgram,keepnote}; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCR; Subkey: ".nbk"; ValueType: string; ValueName: ""; ValueData: "KeepNote_NoteBook"; Flags: uninsdeletevalue
; ".myp" is the extension we're associating. ValueData is the internal name 
; for the file type as stored in the registry. Make sure you use a unique name 
; for this so you don't inadvertently overwrite another application's registry key. 

Root: HKCR; Subkey: "KeepNote_NoteBook"; ValueType: string; ValueName: ""; ValueData: "KeepNote notebook"; Flags: uninsdeletekey
; ValueData above is the name for the file type as shown in Explorer. 

Root: HKCR; Subkey: "KeepNote_NoteBook\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\keepnote.exe,0"
;  "DefaultIcon" is the registry key that specifies the filename containing the icon to associate with the file type. ",0" tells Explorer to use the first icon from MYPROG.EXE. (",1" would mean the second icon.) 

Root: HKCR; Subkey: "KeepNote_NoteBook\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\keepnote.exe"" ""%1""" 

