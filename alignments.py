'''
 Original author of audio sync functions: Allison Deal
 Code adapted from her VideoSync project at:
 https://github.com/allisonnicoledeal/VideoSync
 
 Special thanks to Greg Kramida:
 https://github.com/Algomorph
'''

from PyQt5 import QtWidgets

import scipy.io.wavfile
import numpy as np
import math, tempfile, os, pathlib, subprocess
from urllib.parse import unquote

FFT_BIN_SIZE=1024
OVERLAP=0
BOX_HEIGHT=512
BOX_WIDTH=43
SAMPLES_PER_BOX=7
SUBJECT_DURATION=120
RERFERR_DURATION=60

def extract_audio(dir,clip_mrl: str):
    # print(f"Extract audio from {clip_mrl}.")
    filepath = unquote(clip_mrl.split("//")[-1])
    clip_name = str(os.path.getsize(filepath))  + '_' + os.path.basename(filepath)
    audio_output = ''.join(clip_name.split(".")[:-1]) + "WAV.wav"  # !! CHECK TO SEE IF FILE IS IN UPLOADS DIRECTORY
    outfile = dir + audio_output
    of = pathlib.Path(outfile)
    if of.exists():
        print(f"Wave file {outfile} existed, do nothing.")
    else:
        subprocess.run(["ffmpeg", "-y", "-i", filepath, "-vn", "-ac", "1", "-f", "wav", outfile],stdout = subprocess.DEVNULL,stderr = subprocess.DEVNULL)
    return outfile


# Read file
# INPUT: Audio file
# OUTPUT: Sets sample rate of wav file, Returns data read from wav file (numpy array of integers)
def read_audio(audio_file):
    rate, data = scipy.io.wavfile.read(audio_file)  # Return the sample rate (in samples/sec) and data from a WAV file
    # print(rate)
    return data, rate


def make_horiz_bins(data, fft_bin_size, overlap, box_height):
    horiz_bins = {}
    # process first sample and set matrix height
    sample_data = data[0:fft_bin_size]  # get data for first sample
    if (len(sample_data) == fft_bin_size):  # if there are enough audio points left to create a full fft bin
        intensities = fourier(sample_data)  # intensities is list of fft results
        for i in range(len(intensities)):
            box_y = int(i/box_height)
            if box_y in horiz_bins:
                horiz_bins[box_y].append((intensities[i], 0, i))  # (intensity, x, y)
            else:
                horiz_bins[box_y] = [(intensities[i], 0, i)]
    # process remainder of samples
    x_coord_counter = 1  # starting at second sample, with x index 1
    for j in range(int(fft_bin_size - overlap), len(data), int(fft_bin_size-overlap)):
        sample_data = data[j:j + fft_bin_size]
        if (len(sample_data) == fft_bin_size):
            intensities = fourier(sample_data)
            for k in range(len(intensities)):
                box_y = int(k/box_height)
                if box_y in horiz_bins:
                    horiz_bins[box_y].append((intensities[k], x_coord_counter, k))  # (intensity, x, y)
                else:
                    horiz_bins[box_y] = [(intensities[k], x_coord_counter, k)]
        x_coord_counter += 1
    return horiz_bins


# Compute the one-dimensional discrete Fourier Transform
# INPUT: list with length of number of samples per second
# OUTPUT: list of real values len of num samples per second
def fourier(sample):  #, overlap):
    mag = []
    fft_data = np.fft.fft(sample)  # Returns real and complex value pairs
    for i in range(int(len(fft_data)/2)):
        r = fft_data[i].real**2
        j = fft_data[i].imag**2
        mag.append(round(math.sqrt(r+j),2))

    return mag


def make_vert_bins(horiz_bins, box_width):
    boxes = {}
    for key in horiz_bins.keys():
        for i in range(len(horiz_bins[key])):
            box_x = int(horiz_bins[key][i][1] / box_width)
            if (box_x,key) in boxes:
                boxes[(box_x,key)].append((horiz_bins[key][i]))
            else:
                boxes[(box_x,key)] = [(horiz_bins[key][i])]

    return boxes


def find_bin_max(boxes, maxes_per_box):
    freqs_dict = {}
    for key in boxes.keys():
        max_intensities = [(1,2,3)]
        for i in range(len(boxes[key])):
            if boxes[key][i][0] > min(max_intensities)[0]:
                if len(max_intensities) < maxes_per_box:  # add if < number of points per box
                    max_intensities.append(boxes[key][i])
                else:  # else add new number and remove min
                    max_intensities.append(boxes[key][i])
                    max_intensities.remove(min(max_intensities))
        for j in range(len(max_intensities)):
            if max_intensities[j][2] in freqs_dict:
                freqs_dict[max_intensities[j][2]].append(max_intensities[j][1])
            else:
                freqs_dict[max_intensities[j][2]] = [max_intensities[j][1]]
    return freqs_dict


def find_freq_pairs(freqs_dict_orig, freqs_dict_sample):
    time_pairs = []
    for key in freqs_dict_sample.keys():  # iterate through freqs in sample
        if key in freqs_dict_orig:  # if same sample occurs in base
            for i in range(len(freqs_dict_sample[key])):  # determine time offset
                for j in range(len(freqs_dict_orig[key])):
                    time_pairs.append((freqs_dict_sample[key][i], freqs_dict_orig[key][j]))

    return time_pairs


def find_delay(time_pairs):
    t_diffs = {}
    for i in range(len(time_pairs)):
        delta_t = time_pairs[i][0] - time_pairs[i][1]
        if delta_t in t_diffs:
            t_diffs[delta_t] += 1
        else:
            t_diffs[delta_t] = 1
    t_diffs_sorted = sorted(t_diffs.items(), key=lambda x: x[1])
    time_delay = t_diffs_sorted[-1][0]

    return time_delay

class AdjustClipPosDialog(QtWidgets.QDialog):
    ALIGN_FIRST = 0
    ALIGN_OVERLAP = 1
    ALIGN_LAST = 2

    def __init__(self, clip):
        super().__init__()

        self.clip = clip
        self.setWindowTitle(f"Adjust Time of {clip.name}")
        self.layout = QtWidgets.QVBoxLayout()

        self.layout.addWidget(QtWidgets.QLabel(f'{clip.name} current starats at {clip.durMsStr(clip.sPos)}({clip.sPos/1000})'))


        self.adjTabs = QtWidgets.QTabWidget(self)

        self.manualAdjPage = QtWidgets.QWidget()
        manualPagelayout = QtWidgets.QVBoxLayout()

        inputs = QtWidgets.QHBoxLayout()

        self.direction = QtWidgets.QComboBox(self)
        self.direction.addItem('Delay')
        self.direction.addItem('Advance')

        # seconds = floor(clip.sPos / 1000)
        # minutes = floor(seconds/60)

        self.mins = QtWidgets.QSpinBox(self)
        # self.mins.setValue(floor(minutes))
        self.mins.setMinimum(0)
        self.mins.setMaximum(59)

        self.secs = QtWidgets.QSpinBox(self)
        self.secs.setMinimum(0)
        self.secs.setMaximum(59)
        # self.secs.setValue(seconds - minutes * 60)

        self.ms = QtWidgets.QSpinBox(self)
        self.ms.setMinimum(0)
        self.ms.setMaximum(999)
        # self.ms.setValue(clip.sPos % 1000)

        inputs.addStretch()
        inputs.addWidget(self.direction)
        inputs.addWidget(self.mins)
        inputs.addWidget(QtWidgets.QLabel("m:"))
        inputs.addWidget(self.secs)
        inputs.addWidget(QtWidgets.QLabel("s."))
        inputs.addWidget(self.ms)

        manualPagelayout.addLayout(inputs)
        
        self.manualAdjPage.setLayout(manualPagelayout)
        self.adjTabs.addTab(self.manualAdjPage, "Manual Offsetting")


        self.autoAdjPage = QtWidgets.QWidget()
        autoPagelayout = QtWidgets.QVBoxLayout()
        autoPagelayout.addWidget(QtWidgets.QLabel(f'(Experimental) Auto forward align {clip.name} with:'))
        
        self.tracksBox = QtWidgets.QComboBox()
        self.parentTrack = clip.parent()
        self.tracks = self.parentTrack.parent()
        if len(self.tracks.tracks) > 1:
            for t in self.tracks.tracks:
                if t != self.parentTrack:
                    self.tracksBox.addItem(t.text(), t)
        else:
            self.tracksBox.addItem("Can't do with single track.")
            self.tracksBox.setDisabled(True)

        autoPagelayout.addWidget(self.tracksBox)

        self.alignOption = QtWidgets.QButtonGroup(self.autoAdjPage)
        alignOptionBtns = QtWidgets.QHBoxLayout()
        btn = QtWidgets.QRadioButton("First Match")
        btn.setChecked(True)
        self.alignOption.addButton(btn, self.ALIGN_FIRST)
        alignOptionBtns.addWidget(btn)
        btn = QtWidgets.QRadioButton("Overlaping Clip")
        self.alignOption.addButton(btn, self.ALIGN_OVERLAP)
        alignOptionBtns.addWidget(btn)
        btn = QtWidgets.QRadioButton("Last Match")
        self.alignOption.addButton(btn, self.ALIGN_LAST)
        alignOptionBtns.addWidget(btn)

        autoPagelayout.addLayout(alignOptionBtns)

        self.autoAdjPage.setLayout(autoPagelayout)
        self.adjTabs.addTab(self.autoAdjPage, "Auto Detect (by audio)")


        self.layout.addWidget(self.adjTabs)
        
        QBtn = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        self.buttonBox = QtWidgets.QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)


    def getMS(self) -> int:
        if self.adjTabs.currentWidget() == self.manualAdjPage:
            direction = 1
            if self.direction.currentText() == 'Advance': direction = -1
            offset = ((self.mins.value() * 60 + self.secs.value())*1000 + self.ms.value()) * direction
            print (f'Manually adjusted {self.clip.name} by {offset} ms.')
        elif self.adjTabs.currentWidget() == self.autoAdjPage:
            offset = 0
            refSPos = 0
            milliseconds = 0
            with tempfile.TemporaryDirectory() as tmpdirname:
                print(f'Temporary directory{tmpdirname} created.')

                # The value represents the offset between subject and reference clips
                # Negative value means the subject is ahead of reference.
                milliseconds = 0

                # Process the subject file
                print(f"Trying to allign {self.clip.name}.")
                wavFileS = extract_audio(tmpdirname+'/', self.clip.mrl)
                rawAudioS, rate = read_audio(wavFileS)
                binsDictS = make_horiz_bins(rawAudioS[:44100*SUBJECT_DURATION], FFT_BIN_SIZE, OVERLAP, BOX_HEIGHT)
                boxesS = make_vert_bins(binsDictS, BOX_WIDTH)
                ftDictS = find_bin_max(boxesS, SAMPLES_PER_BOX)
                
                # Loop through reference clips in track
                for c in self.tracksBox.currentData().clips:
                    if c.ePos < self.clip.sPos:
                        print(f"{c.name} skipped, no backward matching.")
                        continue
                    if self.alignOption.checkedId() == self.ALIGN_OVERLAP and c.sPos > self.clip.ePos:
                        print(f"Only compairing overlaping clips, stop now.")
                        break
                    refSPos = c.sPos
                    wavFileR = extract_audio(tmpdirname+'/', c.mrl)
                    rawAudioR, rate = read_audio(wavFileR)
                    binsDictR = make_horiz_bins(rawAudioR[:44100*RERFERR_DURATION], FFT_BIN_SIZE, OVERLAP, BOX_HEIGHT)
                    boxesR = make_vert_bins(binsDictR, BOX_WIDTH)
                    ftDictR = find_bin_max(boxesR, SAMPLES_PER_BOX)

                    # Determie time delay between subject and reference wav file
                    pairs = find_freq_pairs(ftDictS, ftDictR)
                    delay = find_delay(pairs)
                    samples_per_sec = float(rate) / float(FFT_BIN_SIZE)
                    milliseconds = int(round(float(delay) / float(samples_per_sec), 4) * 1000)
                    print(f"Found diff {milliseconds}ms with {c.name}.")

                    if self.alignOption.checkedId() == self.ALIGN_FIRST:
                        print("Matched first clip, stop now.")
                        break

            offset = refSPos - self.clip.sPos + milliseconds

        else:
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Critical)
            msg.setText("Invaild option.")
            msg.setWindowTitle("Error")
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
            return
        return offset
    
    @staticmethod
    def getMsShift(clip):
        dialog = AdjustClipPosDialog(clip)
        result = dialog.exec()
        if result == QtWidgets.QDialog.Accepted:
            return dialog.getMS(), result
        else:
            return 0, result

