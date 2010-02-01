[Setup]
AppName=${PKG}
AppVerName=${PKG} ${VERSION}
AppPublisher=Matt Rasmussen
AppPublisherURL=http://rasm.ods.org/keepnote
DefaultDirName={pf}\${PKG}
DefaultGroupName=${PKG}
DisableProgramGroupPage=true
OutputBaseFilename=keepnote-${VERSION}
Compression=lzma
SolidCompression=true
AllowUNCPath=false
VersionInfoVersion=${VERSION}
VersionInfoCompany=Matt Rasmussen
VersionInfoDescription=${PKG}
ChangesAssociations=yes
OutputDir=dist\
WizardSmallImageFile=keepnote\images\keepnote-48x48.bmp

;WizardImageFile=keepnote\images\keepnote-64x64.bmp
;WizardImageStretch=no
; PrivilegeRequired=admin

[Dirs]
Name: {app}; Flags: uninsalwaysuninstall;

[Files]
Source: dist\keepnote-${VERSION}.win\*; DestDir: {app}; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: {group}\${PKG}; Filename: {app}\keepnote.exe; WorkingDir: {app}

[Run]
Filename: {app}\keepnote.exe; Description: {cm:LaunchProgram,keepnote}; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCR; Subkey: ".nbk"; ValueType: string; ValueName: ""; ValueData: "${PKG}_NoteBook"; Flags: uninsdeletevalue
; ".myp" is the extension we're associating. ValueData is the internal name 
; for the file type as stored in the registry. Make sure you use a unique name 
; for this so you don't inadvertently overwrite another application's registry key. 

Root: HKCR; Subkey: "${PKG}_NoteBook"; ValueType: string; ValueName: ""; ValueData: "${PKG} notebook"; Flags: uninsdeletekey
; ValueData above is the name for the file type as shown in Explorer. 

Root: HKCR; Subkey: "${PKG}_NoteBook\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\keepnote.exe,0"
;  "DefaultIcon" is the registry key that specifies the filename containing the icon to associate with the file type. ",0" tells Explorer to use the first icon from MYPROG.EXE. (",1" would mean the second icon.) 

Root: HKCR; Subkey: "${PKG}_NoteBook\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\keepnote.exe"" ""%1""" 


Root: HKCR; Subkey: ".kne"; ValueType: string; ValueName: ""; ValueData: "${PKG}_Extension"; Flags: uninsdeletevalue
; ".myp" is the extension we're associating. ValueData is the internal name 
; for the file type as stored in the registry. Make sure you use a unique name 
; for this so you don't inadvertently overwrite another application's registry key. 

Root: HKCR; Subkey: "${PKG}_Extension"; ValueType: string; ValueName: ""; ValueData: "${PKG} extension"; Flags: uninsdeletekey
; ValueData above is the name for the file type as shown in Explorer. 

Root: HKCR; Subkey: "${PKG}_Extension\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\keepnote.exe,0"
;  "DefaultIcon" is the registry key that specifies the filename containing the icon to associate with the file type. ",0" tells Explorer to use the first icon from MYPROG.EXE. (",1" would mean the second icon.) 

Root: HKCR; Subkey: "${PKG}_Extension\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\keepnote.exe"" ""%1""" 

