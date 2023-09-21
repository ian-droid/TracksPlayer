from PyQt5 import QtWidgets, QtGui, QtCore, QtMultimedia, QtMultimediaWidgets
import os, time, datetime, operator
from pymediainfo import MediaInfo
from urllib.parse import unquote
from math import floor

class AdjustClipPosDialog(QtWidgets.QDialog):
    def __init__(self, clip):
        super().__init__()

        self.setWindowTitle(f"Adjust Time of {clip.name}")

        QBtn = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addWidget(QtWidgets.QLabel(f'{clip.name} current starats at {clip.durMsStr(clip.sPos)}({clip.sPos/1000})'))

        self.direction = QtWidgets.QComboBox(self)
        self.direction.addItem('+')
        self.direction.addItem('-')

        # seconds = floor(clip.sPos / 1000)
        # minutes = floor(seconds/60)

        self.mins = QtWidgets.QSpinBox(self)
        # self.mins.setValue(floor(minutes))

        self.secs = QtWidgets.QSpinBox(self)
        self.secs.setMinimum(0)
        self.secs.setMaximum(59)
        # self.secs.setValue(seconds - minutes * 60)

        self.ms = QtWidgets.QSpinBox(self)
        self.ms.setMinimum(0)
        self.ms.setMaximum(999)
        # self.ms.setValue(clip.sPos % 1000)

        inputs = QtWidgets.QHBoxLayout()
        inputs.addStretch()
        inputs.addWidget(self.direction)
        inputs.addWidget(self.mins)
        inputs.addWidget(QtWidgets.QLabel("m:"))
        inputs.addWidget(self.secs)
        inputs.addWidget(QtWidgets.QLabel("s."))
        inputs.addWidget(self.ms)

        self.buttonBox = QtWidgets.QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout.addLayout(inputs)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

    def getMS(self) -> int:
        direction = 1
        if self.direction.currentText() == '-': direction = -1
        return ((self.mins.value() * 60 + self.secs.value())*1000 + self.ms.value()) * direction
    
    @staticmethod
    def getMsShift(clip):
        dialog = AdjustClipPosDialog(clip)
        result = dialog.exec()
        return dialog.getMS(), result


class Clip(QtWidgets.QPushButton):
    
    EMPTY = 0
    VIDEO = 1

    SEEKSTEP = 500

    def __init__(self, parent=None, url='', sPos=0, name=None):
        super().__init__(parent)

        self.sPos = sPos
        self.mediatype = Clip.EMPTY
        self.duration = 0
        
        if url[0] == '/':
            self.mrl = "file://" + url
        else:
            self.mrl = url

        mi = MediaInfo.parse(url)
        for t in mi.tracks:
            if t.track_type == "Video":
                self.mediatype = Clip.VIDEO
                self.duration = t.duration
                break

        # calculate the new end position with video length.
        self.ePos = self.sPos + self.duration
        self.name = name if name else unquote(os.path.basename(self.mrl))
        self.setText(self.name)

        self.clicked.connect(self.adjustPosDialog)
        
        # print(f'Clip {self.name} has been placed betweed {self.sPos} and {self.ePos}, a duration of {self.durMsStr()}')

    def durMsStr(self, timeInMS=None):
        if timeInMS == None:
            timeInMS = self.duration
        return str(datetime.timedelta(seconds=timeInMS/1000))
    
    def adjustPosDialog(self):
        msShift, choose = AdjustClipPosDialog.getMsShift(self)
        if choose == QtWidgets.QDialog.Accepted:
            self.adjustPos(msShift)
            self.parent().trackUpdated.emit()

    def adjustPos(self, shiftMS):
        print (f'Move {self.name} by {shiftMS} ms.')
        siblings = self.parent().clips
        # Get the index of current clip, as it must has existed.
        idx = siblings.index(self)
        print (f"Moving the {idx+1} clip of the track...",  end="")
        if (idx == 0 and self.sPos + shiftMS < 0) or (idx > 0 and self.sPos + shiftMS <= siblings[idx-1].ePos):
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Critical)
            msg.setText("Clip can't start before track starts or overlap with the perious one.")
            msg.setWindowTitle("Error")
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
            return
        while idx < len(siblings):
            siblings[idx].sPos += shiftMS
            siblings[idx].ePos += shiftMS
            idx += 1
        # Update the track length.
        self.parent().ePos = siblings[idx-1].ePos
        

class PlayerWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.track = None

        self.videoframe = QtMultimediaWidgets.QVideoWidget()
        self.videoframe.setContentsMargins(0,0,0,0)

        box = QtWidgets.QVBoxLayout()
        box.addWidget(self.videoframe)

        self.setLayout(box)
    
    def setTrack(self, trk):
        self.track = trk

    def keyPressEvent(self, e):
        if self.track.player.state() == QtMultimedia.QMediaPlayer.PlayingState:
            if e.key() == QtCore.Qt.Key_Up:
                vol = self.track.player.volume()
                if  vol <= 90: self.track.player.setVolume(vol+10)
            elif e.key() == QtCore.Qt.Key_Down:
                vol = self.track.player.volume()
                if  vol >= 10: self.track.player.setVolume(vol-10)
            elif e.key() == QtCore.Qt.Key_Right:
                pos = self.track.player.position()
                self.track.player.setPosition( pos + Clip.SEEKSTEP )
                self.track.curClip.adjustPos(Clip.SEEKSTEP)
            elif e.key() == QtCore.Qt.Key_Left:
                pos = self.track.player.position()
                self.track.player.setPosition( pos - Clip.SEEKSTEP )
                self.track.curClip.adjustPos(Clip.SEEKSTEP * -1)
    

class Track(QtWidgets.QLabel):

    # Custom Signals
    trackUpdated = QtCore.pyqtSignal()
    
    def __init__(self, parent=None, trackNo=1):
        super().__init__(parent)
        self.mainWindow = parent.mainWindow
        self.no = trackNo

        # Track has no duration, they share the max duration of tracks.
        self.ePos = 0

        self.clips = []

        self.curClip = None
        self.nextClip = None

        self.setContentsMargins(0,0,0,0)
        self.setText(f"Track {trackNo}")
        if (trackNo % 2):
            self.setStyleSheet("background-color:#E5E4E2")
        else:
            self.setStyleSheet("background-color:#C0C0C0")

        self.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)

        self.setAcceptDrops(True)

        # the QT player
        self.player = QtMultimedia.QMediaPlayer()

        # the Player Window
        self.playerW = PlayerWidget()
        self.playerW.setWindowTitle(f"Track {self.no}")
        qs = QtWidgets.QApplication.primaryScreen()
        swidth = qs.availableSize().width()
        sheight = qs.availableSize().height()
        tw = int(swidth*0.5)
        th = int(sheight*0.5)
        toTop = 70 * int (trackNo / 2  - 0.5) if trackNo > 2 else 0
        if  not trackNo % 2:
            toRight = tw
        else:
            toRight = 0
        self.playerW.setGeometry(toRight, toTop, tw, th)
        # print(f"Resize player window to {tw}x{th}")
        self.player.setVideoOutput(self.playerW.videoframe)

        # Timer use for play next clip.
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.playSchedClip)

        self.player.stateChanged.connect(self.playerStateChange)
        self.playerW.setTrack(self)
        self.playerW.show()


    def addClips(self, clips):
        # Create new Clips from list of dictionary and added them to track.
        for c in clips:
            clip = Clip(self, c['url'], sPos=c['startPosition'], name=c['name'])
            self.clips.append(clip)
            # print(f"{clip.name} ({clip.durMsStr()}) has been added to Track {self.no} (with a width {self.width()}). ")

        # And track end postition need to be updated, otherwise total duration of tracks will fail.
        if clips: self.ePos = max(self.clips, key=operator.attrgetter('ePos')).ePos

    def appendClip(self, clip):
        # Append a clip and extend the track end position
        self.clips.append(clip)
        # Now updated the track duration with end position of the new track.
        self.ePos = clip.ePos
        self.mainWindow.statusBar().showMessage(f"{clip.name} ({clip.durMsStr()}) has been appended to Track {self.no} . ")
        # print(f"{clip.name} ({clip.durMsStr()}) has been appended to Track {self.no} (with a width {self.width()}). ")

    
    def getRightPixByDur(self, dur):
        tWidth = self.width()
        tDur = self.parent().totalDuration
        pix = int( tWidth * ( dur / tDur ) )
        # print(f'Width of all track are {tWidth} pixels for {tDur}ms, {dur}ms takes {pix} pixels.')
        return pix

    def popClipBtn(self):
        # Sort clips to make sure it's in order for the timer.
        self.clips.sort(key=operator.attrgetter('sPos'))
        # Ensure total duration in track is updated for correct calculating
        for c in self.clips:
            c.setContentsMargins(0,0,0,0)
            # c.setCheckable(True)
            c.setToolTip(f'{c.durMsStr(c.sPos)} -> {c.durMsStr(c.ePos)}\n{c.name}({c.durMsStr()})')
            c.setGeometry(QtCore.QRect(QtCore.QPoint(self.getRightPixByDur(c.sPos), 0), QtCore.QSize(self.getRightPixByDur(c.duration), 18)))
            c.show()
            # print(f'Draw a box of {self.getRightPixByDur(c.duration)}x18 and placed at {self.getRightPixByDur(c.sPos)} pix from right for {c.name}({c.duration})')

    def getClipsByPos(self, tpos):
        # return the current clip and next clip at pos of tracks, if NA, return None.
        #Assuming Blank Track.
        cC = None
        nC = None
        # print(f'Getting clips at {tpos}:')
        for c in self.clips:
            if c.sPos <= tpos and c.ePos > tpos:
                cC = c
                continue
            if c.sPos > tpos:
                nC = c
                break
        return [cC, nC]

    def play(self, tPos):
        # Play the current media of track from given position(of the Tracks).
        self.player.setMedia(QtMultimedia.QMediaContent(QtCore.QUrl(self.curClip.mrl)))
        # set the position of media if appliable (A/V)
        # calculated by minus the currnet postion and clip sPos
        absPos = tPos - self.curClip.sPos
        if absPos > 1000:
            self.player.setPosition(absPos)
            print(f'Seeked to {absPos} of {self.curClip.name}, playing...')
        # print(f"Track.{self.no}: Player state: {self.player.state()}")
        self.playerW.setWindowTitle(f'Track {self.no}: {self.curClip.name}')
        self.playerW.show()
        self.player.play()
        self.playerW.setWindowState(QtCore.Qt.WindowActive)

    def schNC(self, nextClip):
        # Set the timer for next clip (playSchedClip()).
        self.nextClip = nextClip
        tpos = self.parent().getCurPos() 
        intV = self.nextClip.sPos - tpos
        self.timer.setInterval(intV)
        self.timer.start()
        print(f'Track {self.no}: Timer set for {nextClip.name}, with a interval of {intV}.')
    
    def playFrom(self, tpos):
        # Play from the given position. 
        # If not a empty track:
        if len(self.clips) > 0:
            # Play from given position of the tracks.
            # First, get the CLIPs at the given position.
            cps = self.getClipsByPos(tpos)
            cP = cps[0]
            nP = cps[1]
            # print(cps, self.curClip, self.nextClip)
            
            if cP == None:
                # Schedule the next clip if there has.
                print(f'Track.{self.no}: Nothing to play now.')
                self.curClip = None
                self.playerW.hide()
            elif self.curClip == cP:
                # If it's the current Clip of the track, then open the media for play.
                print(f'Track.{self.no}: Resume the current media {self.curClip.name} from tracks postion {tpos}.')
                self.play(tpos)
            else:
                # Replace the current media, and play.
                print(f'Track.{self.no}: Replace {self.curClip} with {cP} and play from {tpos}.')
                self.curClip = cP
                self.play(tpos)

            # if there's Next Clip, sechedue it.
            if nP:
                self.schNC(nP)
            elif not self.curClip:
                self.playerW.hide()

    def playerStateChange(self):
        if self.player.state() == QtMultimedia.QMediaPlayer.StoppedState: # and self.nextClip == None:
            self.playerW.hide()

    def playSchedClip(self):
        # trigger by timer
        # Load media from the Next CLIP and set as current media of the track.
    
        self.curClip = self.nextClip
        self.nextClip = None

        # Play immediately from start. Next Clip will be prepared in play().
        print(f'Track.{self.no}: Playing scheduled media {self.curClip.name}.')
        self.player.setMedia(QtMultimedia.QMediaContent(QtCore.QUrl(self.curClip.mrl)))
        self.playerW.setWindowTitle(f'Track {self.no}: {self.curClip.name}')
        self.playerW.show()
        self.player.play()
        nC = self.getClipsByPos(self.curClip.sPos)[1]
        if nC:
            print(f'Track.{self.no}: Got next clip {nC.name}, schedule it.')
            self.schNC(nC)
        
    def pause(self):
        if self.player.pause: self.player.pause()
        self.curClipPausePos = self.parent().getCurPos()
        # Clear the timer.
        self.timer.stop()

    def dragEnterEvent(self, event):
        self.mainWindow.statusBar().showMessage(f"Drop file(s) to add to Track {self.no} for playing.")
        event.accept()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            filename = url.toLocalFile()
            clip = Clip(self, filename, sPos=self.ePos + 1) # Added 1ms to avoid timer overlapping.
            durationInMs = clip.duration
            if durationInMs > 0 :
                # Create a new Clip (button) at the end of track (self.ePos).
                self.appendClip(clip)

        # Need to update tracks first for updating total duration used in calculate the width of clips!
        self.trackUpdated.emit()
        # Update btns in all tracks in event dealing in Tracks, not here!

    def closeTrack(self):
        self.playerW.close()


class Tracks(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.mainWindow = parent
        self.tracks = []

        # Overall playing info
        self.totalDuration = 0

        self.isPlaying = False
        self.pbSpeedF = 1

        #nano seconds for play position, relay on the system clock.
        # Play started postion in ms
        self.resumeFrom = 0
        # Play started time in ns
        self.resumeMomentNS = 0


        self.tracksBox = QtWidgets.QVBoxLayout()
        self.tracksBox.setSpacing(0)

        self.positionSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)

        # self.ruler = QtWidgets.QLabel(self)
        # self.ruler.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))

        centerBox = QtWidgets.QVBoxLayout()
        centerBox.addStretch()
        centerBox.addLayout(self.tracksBox)
        # centerBox.addWidget(self.ruler)
        centerBox.addWidget(self.positionSlider)

        self.setLayout(centerBox)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Maximum)

        self.addTrack()

        self.positionSlider.sliderPressed.connect(self.startSlide)
        self.positionSlider.sliderReleased.connect(self.slided)

    def getTracksList(self):
        ts = []
        for t in self.tracks:
            track = {}
            track['Number'] = t.no
            track['Clips'] = []
            for c in t.clips:
                clip = {}
                clip['name'] = c.name
                clip['url'] = c.mrl
                clip['startPosition'] = c.sPos
                clip['duration'] = c.duration
                clip['type'] = c.mediatype
                track['Clips'].append(clip)
            ts.append(track)
        return ts
    
    def loadTracks(self, tracks):
        self.closeAllTracks()
        for t in tracks:
            self.addTrack(t)
   
    def getCurPos(self):
        # return cur position in ms.
        if self.isPlaying:
            return self.resumeFrom + int((time.time_ns()-self.resumeMomentNS)/1000000)
        else:
            return self.resumeFrom

    def resumePlay(self):
        # call play on all tracks here.
        print(f'Resume play from {self.resumeFrom}.')
        for t in self.tracks:
            t.playFrom(self.resumeFrom)
        self.isPlaying = True
        self.resumeMomentNS = time.time_ns()
        self.updateWidgets()
    
    def pausePlay(self):
        # call pause on all tracks here.
        self.resumeFrom = self.getCurPos()
        for t in self.tracks:
            t.pause()
        self.isPlaying = False
        self.updateWidgets()
        print(f'Paused at {self.resumeFrom}.')


    def addTrack(self, t = None):
        # Add tracks with a dictionary (from Yaml), or an empty track.
        if (t == None or t == False): # add an empty track, when tiggered by the button, it hase the clicked = False parameter.
            trackNo = len(self.tracks) + 1
            track = Track(self, trackNo)
        else:
            trackNo = t['Number']
            track = Track(self, trackNo)
            track.addClips(t['Clips'])

        # The costomized signal
        track.trackUpdated.connect(self.updateWidgets)

        self.tracks.append(track)
        self.tracksBox.addWidget(track)

        track.show()
        self.mainWindow.statusBar().showMessage(f"Added Track {trackNo}.")

    def updateWidgets(self):
        # print(self.tracks[0].width())
        # if self.isPlaying: self.pausePlay()
        self.totalDuration = max(self.tracks, key=operator.attrgetter('ePos')).ePos
        totalDurS = int(self.totalDuration/1000)
        self.mainWindow.progressClock.setText(str(datetime.timedelta(seconds=self.getCurPos()/1000)) + "/" + str(datetime.timedelta(seconds=totalDurS)))
        
        if self.totalDuration > 0:
            self.positionSlider.setRange(0, totalDurS)
            self.positionSlider.setSingleStep(5)
            self.positionSlider.setDisabled(False)
        else:
            self.positionSlider.setDisabled(True)

        for t in self.tracks:
            t.popClipBtn()

        # self.drawRuler()
    
    # def getRightPixByDur(self, dur):
    #     tWidth = self.width()
    #     tDur = self.totalDuration
    #     pix = int( tWidth * ( dur / tDur ) )
    #     # print(f'Width of all tracks width are {tWidth} pixels for {tDur}ms, {dur}ms takes {pix} pixels.')
    #     return pix
 
    # def drawRuler(self):
    #     rwidth = self.positionSlider.width()
    #     rheight = 18
    #     canvas = QtGui.QPixmap(rwidth, rheight)
    #     canvas.fill(self.palette().color(self.backgroundRole()))
    #     painter = QtGui.QPainter(canvas)
    #     painter.drawLine(0, rheight-1, rwidth, rheight-1)
    #     painter.drawLine(0, 0, 0, rheight)
    #     painter.drawLine(rwidth-1, 0, rwidth-1, rheight)
    #     painter.end()
    #     self.ruler.setPixmap(canvas)

    def startSlide(self):
        print("Slide started.")
        self.pausePlay()

    def slided(self):
        self.resumeFrom = self.positionSlider.value()*1000
        print(f"Slided to {self.resumeFrom}.")
        self.resumePlay()
        
    def closeAllTracks(self):
        for t in self.tracks:
            t.closeTrack()
            t.setParent(None)
        self.tracks = []
        self.resumeFrom = 0
        self.totalDuration = 0
        self.positionSlider.setValue(0)
