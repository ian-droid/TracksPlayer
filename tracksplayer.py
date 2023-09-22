import sys

from PyQt5 import QtWidgets, QtGui, QtCore
import os, time, datetime, operator
import yaml

from tracks import *

class Player(QtWidgets.QMainWindow):
    """A simple player for video tracks using VLC and Qt
    """
        
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tracks Player")
        # self.setWindowFlags(QtCore.Qt.FramelessWindowHint)

        self.widget = QtWidgets.QWidget(self)
                
        self.tracks = Tracks(self)

        self.tracks.workingDirectory = os.getcwd()

        self.createUI()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.updateStatus)
        self.timer.start(1000)

    def createUI(self):
        # Buttons and Dial
        self.ppBtn = QtWidgets.QPushButton("⏵", self)
        self.ppBtn.setCheckable(False)
        self.ppBtn.setFixedSize(50, 30)
       
        # The "Clock" for progress with style.
        self.progressClock = QtWidgets.QLabel(self)
        # self.progressClock.setMaximumHeight(30)

        markerLabel = QtWidgets.QLabel("↘️︎:", self)
        self.markerPos = QtWidgets.QLabel(self)
        self.markerPos.setToolTip("In player window, use Ctrl + mouse click to set marker, Shift + mouse click to sync to marker, and Alt + mouse click to clear the marker.s")
 
        self.addTrackBtn = QtWidgets.QPushButton("+", self)
        self.addTrackBtn.setCheckable(False)
        self.addTrackBtn.setFixedSize(50, 30)
        self.addTrackBtn.setToolTip("Add a new blank track.")


        self.saveTracksBtn = QtWidgets.QPushButton("💾︎", self)
        self.saveTracksBtn.setCheckable(False)
        self.saveTracksBtn.setFixedSize(50, 30)
        self.saveTracksBtn.setToolTip("Save the track(s) to a file.")

        self.newTracksBtn = QtWidgets.QPushButton("🗋", self)
        self.newTracksBtn.setCheckable(False)
        self.newTracksBtn.setFixedSize(50, 30)
        self.newTracksBtn.setToolTip("Clear all tracks.")

        self.speedDial = QtWidgets.QDial(self)
        self.speedDial.setMinimum(0)
        self.speedDial.setMaximum(2)
        self.speedDial.setValue(self.tracks.pbSpeedF)
        self.speedDial.setDisabled(True)
        self.speedDial.setToolTip("Playback speed dial (unimplemented.).")

        self.sttBar= QtWidgets.QStatusBar(self)
        # self.sttBar.addPermanentWidget(self.progressClock)
        self.setStatusBar(self.sttBar)
        self.sttBar.showMessage(f"Drop .tracks file or drop media file(s) to Track(s) for playing.")


        # Manage the layouts
        controlsBox = QtWidgets.QHBoxLayout()
        controlsBox.addWidget(self.ppBtn)
        controlsBox.addWidget(self.progressClock)
        controlsBox.addSpacing(20)
        controlsBox.addWidget(markerLabel)
        controlsBox.addWidget(self.markerPos)
        controlsBox.addStretch()
        controlsBox.addWidget(self.addTrackBtn)
        controlsBox.addWidget(self.saveTracksBtn)
        controlsBox.addWidget(self.speedDial)
        controlsBox.addWidget(self.newTracksBtn)
        
        centerBox = QtWidgets.QVBoxLayout()
        centerBox.addWidget(self.tracks)
        centerBox.addLayout(controlsBox)

        self.widget.setLayout(centerBox)
        self.setCentralWidget(self.widget)

        # Connect button signals
        self.setAcceptDrops(True)

        self.saveTracksBtn.clicked.connect(self.saveTracksToYaml)
        self.newTracksBtn.clicked.connect(self.newTracks)

        self.ppBtn.clicked.connect(self.playOrPause)
        self.addTrackBtn.clicked.connect(self.tracks.addTrack)

    def refreshUI(self):
        self.progressClock.setText(str(datetime.timedelta(seconds=self.tracks.getCurPos()/1000)) + "/" + str(datetime.timedelta(seconds=self.tracks.totalDuration/1000)))
        self.tracks.updateWidgets()

    def playOrPause(self):
        if (not self.tracks.isPlaying) and self.tracks.totalDuration > 0:
            self.sttBar.showMessage(f'Start playing from {str(datetime.timedelta(seconds=int(self.tracks.resumeFrom/1000)))}.')
            self.tracks.resumePlay()
            self.ppBtn.setText("⏸︎")
        else:
            self.sttBar.showMessage(f'Pausing at {str(datetime.timedelta(seconds=int(self.tracks.getCurPos()/1000)))}.')
            self.tracks.pausePlay()
            self.ppBtn.setText("⏵")

    def stopAll(self):
        self.tracks.pausePlay()
        self.tracks.resumeFrom = 0
        self.ppBtn.setText("⏵")
        self.tracks.positionSlider.setValue(0)
        self.sttBar.showMessage("Play stopped.")

    def updateStatus(self):
        if self.tracks.isPlaying:
            pos = self.tracks.getCurPos()
            posS = int(pos/1000)
            self.tracks.positionSlider.setValue(posS)
            self.progressClock.setText(str(datetime.timedelta(seconds=posS)) + "/" + str(datetime.timedelta(seconds=int(self.tracks.totalDuration/1000))))
            if pos >= self.tracks.totalDuration:
                self.stopAll()
            self.ppBtn.setText("⏸︎")
        else:
            self.ppBtn.setText("⏵")
        
        self.markerPos.setText(str(datetime.timedelta(seconds=self.tracks.marker/1000)))
            
    def saveTracksToYaml(self):
        fname = QtWidgets.QFileDialog.getSaveFileName(self, caption='Save Track(s)', filter="Tracks Files (*.tracks)")
        tFile = {'Version': 1, 'Timestamp': int(time.time())}
        tracks = self.tracks.getTracksList()
        tFile['Tracks']=tracks
        file = open(fname[0],'w')
        file.write(yaml.dump(tFile))
        file.close()
        self.sttBar.showMessage(f'Tracks info saved to {fname[0]}.')

    def newTracks(self):
        self.tracks.closeAllTracks()
        self.tracks.addTrack()

    def dragEnterEvent(self, event):
        self.statusBar().showMessage(f"Drop .tracks file to load Tracks.")
        if event.mimeData().hasFormat('text/plain'):
            event.accept()

    def dropEvent(self, event):
        fname = event.mimeData().urls()[0].toLocalFile()
        file = open(fname, 'r')
        try:
            tFile = yaml.safe_load(file)
        except:
            file.close()
            self.statusBar().showMessage('Error parsing .tracks File.')
            return
        file.close()
        # print(type(tracks))
        self.tracks.loadTracks(tFile['Tracks'])
        self.refreshUI()
    
    def closeEvent(self, event):
        self.tracks.closeAllTracks()
        return super().closeEvent(event)


def main():
    app = QtWidgets.QApplication([])

    app.setFont(QtGui.QFont("Mono", 10))
    
    swidth = app.primaryScreen().size().width()
    sheight = app.primaryScreen().size().height()
    height = 150
    
    player = Player()
    
    player.resize(swidth, height)
    player.move(0,sheight-height-50)
    
    player.show()
    player.refreshUI()

    app.exec_()

if __name__ == "__main__":
    main()