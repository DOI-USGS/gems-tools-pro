# Keeping up to date with new releases
Instead of downloading new releases as zip files when you know there has been a change to a tool or a new tool has been added, instead
1. Get automatic [notifications](#notifications-of-new-releases) of new releases.
2. If you don't already have git on your computer, [install](#install) it.
3. [Clone](#clone) this repository to your computer.
4. Use [`git pull`](#pull) to download changes when you get notified of a new release.

If you need more information, read on:

## Notifications of new releases

New releases for the toolbox are published as-needed when solutions to issues are written or new features are added. You can find out about new releases in two ways.
1. Notice that there is a warning in the geoprocessing messages dialog when you run a tool that it is obsolete and a revised tool has been posted.
2. 'Watch' this repository and get an email when there is a new release.

To watch the repository, first create a GitHub account. When logged in, go to the main page for this [repo](https://github.com/usgs/gems-tools-pro) and look in the upper-right for the Watch button.

![image](https://user-images.githubusercontent.com/5376315/193160743-d7033977-d600-4730-8b7a-f1d20e2fa77f.png)

Click the drop-down button and go down to Custom

![image](https://user-images.githubusercontent.com/5376315/193160864-21b5eb0c-c782-4232-9f1c-8cbcb5a9c703.png)

and then select Releases and Apply:

![image](https://user-images.githubusercontent.com/5376315/193161579-8bc73884-20f4-4045-8829-c0913703717b.png)

To be honest, I don't know if you will get other emails from GitHub just by choosing Watch; it might be too noisy. But try it out and let us know how it works.

## <a name="install"></a> "Install" git

If you don't already have git on your computer, here is a simple way to get and use it that doesn't involve a full-blown installation that requires elevated privileges.
1. [Download](https://git-scm.com/download/win) the **64-bit Git for Windows Portable** version. This downloads as an .exe file that, when double-clicked, extracts the git package to a folder of your choice. Put it anywhere you like and copy the path to the parent folder

![image](https://user-images.githubusercontent.com/5376315/194180266-599a8441-a934-4513-b577-b5f8c3509052.png)

2. In the Windows Search bar on your desktop type 'environment variables' and pick 'Edit environment variables for your account' from the results

![image](https://user-images.githubusercontent.com/5376315/194180560-0a69c9bc-ad06-42a4-bc63-388d4dac6ca4.png)

3. Click on 'Path' and then 'Edit'

![image](https://user-images.githubusercontent.com/5376315/194180748-b886dad0-d12c-4346-bd8c-c6fd124097d0.png)

4. Click 'New' and paste the full path in the highlighted cell to where git was extracted. Click ok.
5. Test that this worked by opening a Windows Command Prompt window. Type 'cmd' in the Windows Search bar. When the results show up, Command Prompt is already selected, so just press Enter to open it.

![image](https://user-images.githubusercontent.com/5376315/194182018-8baa45d0-f0a1-48e5-b69e-1f1c172c5587.png)

Type `git --version` at the prompt and you should get a line like `git version 2.30.0.windows.2`

6. Another option is to ignore setting an environment variable and use git-cmd.exe whenever you need to issue git commands. This file in the \git folder you extracted earlier. It opens a command prompt window configured to work with git. You can drag this file to the taskbar to pin it there for quick access.

![image](https://user-images.githubusercontent.com/5376315/194182956-5c7025fb-8b9a-47ac-9acb-adf249c86023.png)

## Clone the repo

1. With either command prompt window open, navigate to the parent folder where you want the toolbox folder to be using `cd`

2. copy and paste this command:
`git clone https://github.com/usgs/gems-tools-pro.git`

3. type `dir` to see that the `gems-tools-pro` directory has been added

(steps 1 - 3 above)

![image](https://user-images.githubusercontent.com/5376315/194183746-f8d8d1e6-ef3c-4d43-a26d-342e9542defc.png)

_(**USGS users**: when you try to clone, if you get the warning:_

_`fatal: unable to access 'https://github.com/usgs/gems-tools-pro.git/': SSL certificate problem: unable to get local issuer certificate`_

_you are probably connected to a VPN through Pulse Secure. Disconnect and try again)_.

## <a name="pull"></a> Use `git pull` to get changes
Now, whenever you want to update the toolbox, open a command prompt, cd to `gems-tools-pro` and type `git pull`.
To speed this up you could add [create a batch file](https://www.makeuseof.com/tag/write-simple-batch-bat-file/) and save it in the default directory shown when the command prompt opens or [pin](https://superuser.com/questions/100249/how-to-pin-either-a-shortcut-or-a-batch-file-to-the-new-windows-7-8-and-10-task) a shortcut to the batch file to your taskbar.

