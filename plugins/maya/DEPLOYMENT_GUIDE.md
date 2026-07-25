# Studio Deployment Guide (Network Drive Approach)

This guide explains how to deploy the RenderHive Maya Plugin across your studio using a shared network drive. This is the recommended approach for in-house studios as it allows you to update the plugin for all artists instantly without reinstalling it on every machine.

## Step 1: Set Up the Network Share
1. Copy the entire `plugins/maya` folder to your studio's shared network drive. 
   - *Example: `Z:\Pipeline\RenderHive\plugins\maya` or `\\192.168.1.100\shared\RenderHive\plugins\maya`*

## Step 2: Configure the .mod File
1. Open the `RenderHive.mod` file included in this directory.
2. Replace `<NETWORK_DRIVE_PATH>\RenderHive\plugins\maya` with the actual UNC path or mapped drive path from Step 1.
   - *Example:* `+ RenderHive 1.9.7 Z:\Pipeline\RenderHive\plugins\maya`

## Step 3: Deploy to Artists
You only need to distribute the tiny `RenderHive.mod` file to your artists. 

Place the `RenderHive.mod` file into their local Maya modules directory. By default, this is located at:
- **Windows:** `C:\Users\<Username>\Documents\maya\modules`
- **macOS:** `~/Library/Preferences/Autodesk/maya/modules`
- **Linux:** `~/maya/modules`

*(Note: If the `modules` folder does not exist, simply create it).*

## How it works
Next time the artist opens Maya, Maya will read the `.mod` file, follow the path to the network drive, and load the plugin directly from the server.

When you need to fix a bug or add a feature to the plugin, just overwrite the files on the network drive. The next time the artists restart Maya, they will automatically be using the latest version!
