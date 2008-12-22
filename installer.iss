[Setup]
AppName=TakeNote
AppVerName=TakeNote 0.4.5
AppPublisher=Matt Rasmussen
AppPublisherURL=http://people.csail.mit.edu/rasmus/takenote
DefaultDirName={pf}\TakeNote
DefaultGroupName=TakeNote
DisableProgramGroupPage=true
OutputBaseFilename=takenote-0.4.5
Compression=lzma
SolidCompression=true
AllowUNCPath=false
VersionInfoVersion=0.4.5
VersionInfoCompany=Matt Rasmussen
VersionInfoDescription=TakeNote
ChangesAssociations=yes
;WizardImageFile=takenote\images\takenote-64x64.bmp
;WizardImageStretch=no
; PrivilegeRequired=admin

[Dirs]
Name: {app}; Flags: uninsalwaysuninstall;

[Files]
Source: dist\*; DestDir: {app}; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: {group}\TakeNote; Filename: {app}\takenote.exe; WorkingDir: {app}

[Run]
Filename: {app}\takenote.exe; Description: {cm:LaunchProgram,takenote}; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCR; Subkey: ".nbk"; ValueType: string; ValueName: ""; ValueData: "TakeNote_NoteBook"; Flags: uninsdeletevalue
; ".myp" is the extension we're associating. ValueData is the internal name 
; for the file type as stored in the registry. Make sure you use a unique name 
; for this so you don't inadvertently overwrite another application's registry key. 

Root: HKCR; Subkey: "TakeNote_NoteBook"; ValueType: string; ValueName: ""; ValueData: "TakeNote notebook"; Flags: uninsdeletekey
; ValueData above is the name for the file type as shown in Explorer. 

Root: HKCR; Subkey: "TakeNote_NoteBook\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\takenote.exe,0"
;  "DefaultIcon" is the registry key that specifies the filename containing the icon to associate with the file type. ",0" tells Explorer to use the first icon from MYPROG.EXE. (",1" would mean the second icon.) 

Root: HKCR; Subkey: "TakeNote_NoteBook\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\takenote.exe"" ""%1""" 

