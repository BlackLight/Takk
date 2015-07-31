#!/usr/bin/python2

from array import array
from struct import pack
from sys import byteorder
import copy
import pyaudio
import wave

class AudioSource():
    # threshold = 500  # audio levels not normalised.
    threshold = 5000  # audio levels not normalised.
    chunkSize = 1024
    rate = 48000
    silentChunks = 2 * rate / 1024  # about 2 sec
    format = pyaudio.paInt16
    frameMaxValue = 2 ** 15 - 1
    normalizeMinusOneDb = 10 ** (-1.0 / 20)
    channels = 1
    trimAppend = rate / 4
    silentChunksThreshold = 10

    def init(self, threshold=None, chunkSize=None, silentSeconds=3):
        self.threshold = threshold if threshold is not None else __class__.threshold
        self.chunkSize = chunkSize if chunkSize is not None else __class__.chunkSize
        self.silentSeconds = silentSeconds if silentSeconds is not None else __class__.silentSeconds
        self.format = __class__.format
        self.frameMaxValue = __class__.frameMaxValue
        self.normalizeMinusOneDb = __class__.normalizeMinusOneDb
        self.rate = __class__.rate
        self.channels = __class__.channels
        self.trimAppend = __class__.trimAppend

    def __isSilent(self, dataChunk):
        """Returns 'True' if below the 'silent' threshold"""
        return max(dataChunk) < self.threshold

    def __normalize(self, dataAll):
        """Amplify the volume out to max -1dB"""
        # MAXIMUM = 16384
        normalizeFactor = (float(self.normalizeMinusOneDb * self.frameMaxValue)
                            / max(abs(i) for i in dataAll))

        r = array('h')
        for i in dataAll:
            r.append(int(i * normalizeFactor))
        return r

    def __trim(self, dataAll):
        _from = 0
        _to = len(dataAll) - 1
        for i, b in enumerate(dataAll):
            if abs(b) > self.threshold:
                _from = int(max(0, i - self.trimAppend))
                break

        for i, b in enumerate(reversed(dataAll)):
            if abs(b) > self.threshold:
                _to = int(min(len(dataAll) - 1, len(dataAll) - 1 - i + self.trimAppend))
                break

        return copy.deepcopy(dataAll[_from:(_to + 1)])

    def record(self):
        """Record a word or words from the microphone and 
        return the data as an array of signed shorts."""

        p = pyaudio.PyAudio()
        stream = p.open(format=self.format, channels=self.channels, rate=self.rate, input=True, output=True, frames_per_buffer=self.chunkSize)

        silentChunks = 0
        audioStarted = False
        dataAll = array('h')

        while True:
            # little endian, signed short
            dataChunk = array('h', stream.read(self.chunkSize))
            if byteorder == 'big':
                dataChunk.byteswap()
            dataAll.extend(dataChunk)

            silent = self.__isSilent(dataChunk)

            if audioStarted:
                if silent:
                    silentChunks += 1
                    if silentChunks > self.silentChunks:
                        print("AUDIO STOPPED")
                        break
                elif silentChunks > self.silentChunksThreshold:
                    silentChunks = 0
            elif not silent:
                print("AUDIO STARTED")
                audioStarted = True

        sample_width = p.get_sample_size(self.format)
        stream.stop_stream()
        stream.close()
        p.terminate()

        data_all = self.__trim(dataAll)  # we trim before normalize as threshhold applies to un-normalized wave (as well as isSilent() function)
        data_all = self.__normalize(data_all)
        return sample_width, data_all

    def recordToFile(self, path):
        "Records from the microphone and outputs the resulting data to 'path'"
        sample_width, data = self.record()
        data = pack('<' + ('h' * len(data)), *data)

        wave_file = wave.open(path, 'wb')
        wave_file.setnchannels(self.channels)
        wave_file.setsampwidth(sample_width)
        wave_file.setframerate(self.rate)
        wave_file.writeframes(data)
        wave_file.close()

