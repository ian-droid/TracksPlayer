# TracksPlayer

A simple multi-tracks video player with minimal function set to play video files like in video editors.

Written in Python with PyQt5, it's just working: barely no exception handling. And it's only been tested under Debian Bookworm. For Windows users, you may need additional codec to make Qt Media Player working or you will have a empty player window.

## Requirements 
- Python3 (3.7+)
- PyQt5
- YAML
- MediaInfo

## Usage Tips
- Drag & drop (video) file(s) into a track for playing.
- Drop .tracks file to the main window to load saved track(s). The track(s) info are saved in YAML file, so the playing sequence can be edited with text editors (before the GUI is fully Functional).
- Click on the cilp (yes, they are presented as buttons for now), you can set advance or delay the start position of the clip in the timeline. However, for now, the change is cascaded on the following clips if there's any.
- Clip alignment can also be adjusted with a marker: In player window, use Ctrl + mouse click to mark the current position as target position, then you can use Shift + mouse click in (other) player window at the moment you want to align with the previous marked target position. And Alt + mouse click in any player window to clear the marker (set to 0:00:00).
- Up/Down arrow keys can adjust the sound volume of the focused player window (track); Left/Right arrow keys can seek the current playing clip (in a step of 1 second), while this also changes the position of the clip in the timeline, and this function is unreliable.
 

## To Do
- Frameless player window.
- Improve the UI, especially for Windows, as it's not displayed as proper as in Debian with scaled 4K desktop.
- Better window management: main window start position, and (auto) arrangement of opened player window(s).
- Draggable clips.