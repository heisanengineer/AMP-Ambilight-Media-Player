import colorsys
import wcag_contrast_ratio as contrast
import numpy as np
import numpy
import math
from sklearn.cluster import KMeans
from collections import Counter
import time
import cv2
import sys
import os
import wcag_contrast_ratio as contrast
import colorsys
from PIL import Image
from os.path import exists
from configparser import ConfigParser
import PyQt5
from PyQt5 import QtCore, QtWidgets
from PyQt5 import QtGui
from PyQt5.QtCore import * 
from PyQt5.QtGui import * 
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QUrl, Qt
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QFileDialog
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer, QVideoFrame, QAbstractVideoSurface, QAbstractVideoBuffer, QVideoSurfaceFormat
from threading import Thread
import yeelight
import time
from yeelight.main import Bulb
from yeelight.main import discover_bulbs
from yeelight import enums

class DominantColors:
    CLUSTERS = None
    IMAGE = None
    COLORS = None
    LABELS = None
    def __init__(self, image, clusters=3):
        self.CLUSTERS = clusters
        self.IMAGE = image
    def dominantColors(self):
        # read image
        img_src = cv2.imread(self.IMAGE)
        # percent by which the image is resized
        scale_percent = 10
        # calculate the 50 percent of original dimensions
        width = int(img_src.shape[1] * scale_percent / 100)
        height = int(img_src.shape[0] * scale_percent / 100)
        # dsize
        dsize = (width, height)
        # resize image
        small_img = cv2.resize(img_src, dsize)
        # convert to rgb from bgr
        img = cv2.cvtColor(small_img, cv2.COLOR_BGR2RGB)
        # reshaping to a list of pixels
        img = img.reshape((img.shape[0] * img.shape[1], 3))
        # save image after operations
        self.IMAGE = img
        # using k-means to cluster pixels
        kmeans = KMeans(n_clusters=self.CLUSTERS)
        kmeans.fit(img)
        # the cluster centers are our dominant colors.
        self.COLORS = kmeans.cluster_centers_
        # save labels
        self.LABELS = kmeans.labels_
        # returning after converting to integer from float
        return self.COLORS.astype(int)

class VideoFrameGrabber(QAbstractVideoSurface):
    frameAvailable = pyqtSignal(QImage)
    def __init__(self, widget: QWidget, parent: QObject):
        super().__init__(parent)
        self.widget = widget
    def supportedPixelFormats(self, handleType):
        return [QVideoFrame.Format_ARGB32, QVideoFrame.Format_ARGB32_Premultiplied,
                QVideoFrame.Format_RGB32, QVideoFrame.Format_RGB24, QVideoFrame.Format_RGB565,
                QVideoFrame.Format_RGB555, QVideoFrame.Format_ARGB8565_Premultiplied,
                QVideoFrame.Format_BGRA32, QVideoFrame.Format_BGRA32_Premultiplied, QVideoFrame.Format_BGR32,
                QVideoFrame.Format_BGR24, QVideoFrame.Format_BGR565, QVideoFrame.Format_BGR555,
                QVideoFrame.Format_BGRA5658_Premultiplied, QVideoFrame.Format_AYUV444,
                QVideoFrame.Format_AYUV444_Premultiplied, QVideoFrame.Format_YUV444,
                QVideoFrame.Format_YUV420P, QVideoFrame.Format_YV12, QVideoFrame.Format_UYVY,
                QVideoFrame.Format_YUYV, QVideoFrame.Format_NV12, QVideoFrame.Format_NV21,
                QVideoFrame.Format_IMC1, QVideoFrame.Format_IMC2, QVideoFrame.Format_IMC3,
                QVideoFrame.Format_IMC4, QVideoFrame.Format_Y8, QVideoFrame.Format_Y16,
                QVideoFrame.Format_Jpeg, QVideoFrame.Format_CameraRaw, QVideoFrame.Format_AdobeDng]

    def isFormatSupported(self, format):
        imageFormat = QVideoFrame.imageFormatFromPixelFormat(format.pixelFormat())
        size = format.frameSize()
        return imageFormat != QImage.Format_Invalid and not size.isEmpty() and format.handleType() == QAbstractVideoBuffer.NoHandle

    def start(self, format: QVideoSurfaceFormat):
        imageFormat = QVideoFrame.imageFormatFromPixelFormat(format.pixelFormat())
        size = format.frameSize()
        if imageFormat != QImage.Format_Invalid and not size.isEmpty():
            self.imageFormat = imageFormat
            self.imageSize = size
            self.sourceRect = format.viewport()
            super().start(format)
            self.widget.updateGeometry()
            self.updateVideoRect()
            return True
        else:
            return False
    def stop(self):
        self.currentFrame = QVideoFrame()
        self.targetRect = QRect()
        #super().stop()
        self.widget.update()

    def present(self, frame):
        if frame.isValid():
            cloneFrame = QVideoFrame(frame)
            cloneFrame.map(QAbstractVideoBuffer.ReadOnly)
            image = QImage(cloneFrame.bits(), cloneFrame.width(), cloneFrame.height(),
                           QVideoFrame.imageFormatFromPixelFormat(cloneFrame.pixelFormat()))
            self.frameAvailable.emit(image)  # this is very important
            cloneFrame.unmap()

        if self.surfaceFormat().pixelFormat() != frame.pixelFormat() or self.surfaceFormat().frameSize() != frame.size():
            self.setError(QAbstractVideoSurface.IncorrectFormatError)
            #self.stop()
            return False
        else:
            self.currentFrame = frame
            self.widget.repaint(self.targetRect)
            return True
    def updateVideoRect(self):
        size = self.surfaceFormat().sizeHint()
        size.scale(self.widget.size().boundedTo(size), Qt.KeepAspectRatio)

        self.targetRect = QRect(QPoint(0, 0), size)
        self.targetRect.moveCenter(self.widget.rect().center())

    def paint(self, painter):
        if self.currentFrame.map(QAbstractVideoBuffer.ReadOnly):
            oldTransform = self.painter.transform()

        if self.surfaceFormat().scanLineDirection() == QVideoSurfaceFormat.BottomToTop:
            self.painter.scale(1, -1)
            self.painter.translate(0, -self.widget.height())

        image = QImage(self.currentFrame.bits(), self.currentFrame.width(), self.currentFrame.height(),
                       self.currentFrame.bytesPerLine(), self.imageFormat)

        self.painter.drawImage(self.targetRect, image, self.sourceRect)
        self.painter.setTransform(oldTransform)
        self.currentFrame.unmap()

class VideoWidget(QVideoWidget):
    def __init__(self, parent=None):
        super(VideoWidget, self).__init__(parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        #self.setStyleSheet("background-color: black")
        p = self.palette()
        p.setColor(QPalette.Window, Qt.black)
        self.setPalette(p)
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.isFullScreen():
            self.setFullScreen(False)
            event.accept()
        elif event.key() == Qt.Key_U:
            self.setFullScreen(not self.isFullScreen())
            event.accept()
        else:
            super(VideoWidget, self).keyPressEvent(event)
    def mouseDoubleClickEvent(self, event):
        self.setFullScreen(not self.isFullScreen())
        event.accept()

class AL_Player(QtWidgets.QMainWindow):
    def __init__(self):
        self.bulb1 = Bulb("192.168.1.33", effect="smooth")
        self.bulb2 = Bulb("192.168.1.39", effect="smooth")
        try:
            self.bulb1.stop_music()
            self.bulb2.stop_music()
        except:
            pass
        time.sleep(1)
        self.bulb1.start_music(20000)
        self.bulb2.start_music(20000)

        self.bulb1.turn_off()
        self.bulb2.turn_off()
        super(AL_Player, self).__init__()
        uic.loadUi('407.ui', self)
        self.mainWindow = self.findChild(QtWidgets.QMainWindow, 'MainWindow')
        self.settingsBox = self.findChild(QtWidgets.QGroupBox, 'settingsBox')
        self.settingsBox.setVisible(False)
        self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.videoWidget = VideoWidget()
        self.videoWidget.setStyleSheet("background-color: black")
        self.grabber = VideoFrameGrabber(self.videoWidget, self)
        self.mediaPlayer.setVideoOutput([self.videoWidget.videoSurface(),self.grabber])
        self.grabber.frameAvailable.connect(self.process_frame)

        #self.mediaPlayer.stateChanged.connect(self.StateChanged)
        self.mediaPlayer.positionChanged.connect(self.positionChanged)
        self.mediaPlayer.durationChanged.connect(self.durationChanged)
        self.mediaPlayer.volumeChanged.connect(self.volumeChanged)
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
        self.vLayout = self.findChild(QtWidgets.QVBoxLayout, 'playvideoLayout')
        self.vLayout.addWidget(self.videoWidget)
        self.setFixedWidth(594)
        self.setFixedHeight(500)
        self.show()

        self.LeftTopLamp = self.findChild(QtWidgets.QPushButton, 'LeftTopLamp')
        self.LeftBottomLamp = self.findChild(QtWidgets.QPushButton, 'LeftBottomLamp')
        self.RightTopLamp = self.findChild(QtWidgets.QPushButton, 'RightTopLamp')
        self.RightBottomLamp = self.findChild(QtWidgets.QPushButton, 'RightBottomLamp')

        self.openmenu = self.findChild(QtWidgets.QAction, 'actionOpen')
        self.openmenu.triggered.connect(self.openFile)

        self.savesettingmenu = self.findChild(QtWidgets.QAction, 'actionSettings')
        self.savesettingmenu.triggered.connect(self.saveSettings)

        self.openmenu = self.findChild(QtWidgets.QAction, 'actionExit')
        self.openmenu.triggered.connect(self.exitFun)
        
        self.openbutton = self.findChild(QtWidgets.QPushButton, 'openButton')
        self.openbutton.clicked.connect(self.openFile)

        self.playbutton = self.findChild(QtWidgets.QPushButton, 'playButton')
        self.playbutton.clicked.connect(self.playclick)

        self.pausebutton = self.findChild(QtWidgets.QPushButton, 'pauseButton')
        self.pausebutton.clicked.connect(self.pauseclick)

        self.stopButton = self.findChild(QtWidgets.QPushButton, 'stopButton')
        self.stopButton.clicked.connect(self.stopclick)

        self.fullscrbutton = self.findChild(QtWidgets.QPushButton, 'fullscrButton')
        self.fullscrbutton.clicked.connect(self.fullscreen)

        self.firstButton = self.findChild(QtWidgets.QPushButton, 'firstButton')
        self.firstButton.clicked.connect(self.setFirst)

        self.lastButton = self.findChild(QtWidgets.QPushButton, 'lastButton')
        self.lastButton.clicked.connect(self.setLast)

        self.preButton = self.findChild(QtWidgets.QPushButton, 'preButton')
        self.preButton.clicked.connect(self.setPrev)

        self.nextButton = self.findChild(QtWidgets.QPushButton, 'nextButton')
        self.nextButton.clicked.connect(self.setNext)

        self.testButton = self.findChild(QtWidgets.QPushButton, 'testButton')
        self.testButton.clicked.connect(self.testLamp)

        self.settingsButton = self.findChild(QtWidgets.QPushButton, 'settingsButton')
        self.settingsButton.clicked.connect(self.showSettings)
        
        self.saveSetButton = self.findChild(QtWidgets.QPushButton, 'saveSetButton')
        self.saveSetButton.clicked.connect(self.saveSettings)

        self.discoverButton = self.findChild(QtWidgets.QPushButton, 'discoverButton')
        self.discoverButton.clicked.connect(self.discoverBulbs)
        
        self.progressSlider = self.findChild(QtWidgets.QSlider, 'progressSlider')
        self.progressSlider.sliderMoved.connect(self.setPosition)

        self.volumeSlider = self.findChild(QtWidgets.QSlider, 'volumeSlider')
        self.volumeSlider.sliderMoved.connect(self.setVolume)

        self.LeftTopBox = self.findChild(QtWidgets.QCheckBox,'LeftTopBox')
        self.RightTopBox = self.findChild(QtWidgets.QCheckBox,'RightTopBox')
        self.LeftBottomBox = self.findChild(QtWidgets.QCheckBox,'LeftBottomBox')
        self.RightBottomBox = self.findChild(QtWidgets.QCheckBox,'RightBottomBox')

        self.LeftTopIpEdit = self.findChild(QtWidgets.QLineEdit,'LeftTopIpEdit')
        self.RightTopIpEdit = self.findChild(QtWidgets.QLineEdit,'RightTopIpEdit')
        self.LeftBottomIpEdit = self.findChild(QtWidgets.QLineEdit,'LeftBottomIpEdit')
        self.RightBottomIpEdit = self.findChild(QtWidgets.QLineEdit,'RightBottomIpEdit')
        
        if exists('settings.ini') :
            try:
                getObject = ConfigParser()
                getObject.read("settings.ini")
            
                lTop = getObject["LEFTTOP"]
                
                if lTop["checked"]=="True":
                    self.LeftTopBox.setChecked(True)
                else:
                    self.LeftTopBox.setChecked(False)
                self.LeftTopIpEdit.setText(lTop["ip"])

                lBottom = getObject["LEFTBOTTOM"]
                if lBottom["checked"]=="True":
                    self.LeftBottomBox.setChecked(True)
                else:
                    self.LeftBottomBox.setChecked(False)
                self.LeftBottomIpEdit.setText(lBottom["ip"])

                rTop = getObject["RIGHTTOP"]
                if rTop["checked"]=="True":
                    self.RightTopBox.setChecked(True)
                else:
                    self.RightTopBox.setChecked(False)
                self.RightTopIpEdit.setText(rTop["ip"])

                rBottom = getObject["RIGHTBOTTOM"]
                if rBottom["checked"]=="True":
                    self.RightBottomBox.setChecked(True)
                else:
                    self.RightBottomBox.setChecked(False)
                self.RightBottomIpEdit.setText(rBottom["ip"])
            except:
                pass
    
    def sendColor(self):
        img = 'l1.png'
        clusters = 1
        dc = DominantColors(img, clusters) 
        ltcolors = dc.dominantColors()
        img = 'r3.png'
        
        dc = DominantColors(img, clusters) 
        rtcolors = dc.dominantColors()

        self.bulb1.set_rgb(int(ltcolors[0,0]),int(ltcolors[0,1]),int(ltcolors[0,2]))
        self.bulb2.set_rgb(int(rtcolors[0,0]),int(rtcolors[0,1]),int(rtcolors[0,2]))

    def process_frame(self, image):
        self.divideImage4part(self.convertQImageToMat(image))
        self.sendColor()

    def divideImage4part(self,img):
        height = img.shape[0]
        width = img.shape[1]
        width_cutoff = width // 2
        left1 = img[:, :width_cutoff]
        right1 = img[:, width_cutoff:]
        img = cv2.rotate(left1, cv2.ROTATE_90_CLOCKWISE)
        height = img.shape[0]
        width = img.shape[1]
        width_cutoff = width // 2
        l2 = img[:, :width_cutoff]
        l1 = img[:, width_cutoff:]
        l2 = cv2.rotate(l2, cv2.ROTATE_90_COUNTERCLOCKWISE)
        cv2.imwrite("l2.png", l2)
        l1 = cv2.rotate(l1, cv2.ROTATE_90_COUNTERCLOCKWISE)
        cv2.imwrite("l1.png", l1)
        img = cv2.rotate(right1, cv2.ROTATE_90_CLOCKWISE)
        height = img.shape[0]
        width = img.shape[1]
        width_cutoff = width // 2
        r4 = img[:, :width_cutoff]
        r3 = img[:, width_cutoff:]
        r4 = cv2.rotate(r4, cv2.ROTATE_90_COUNTERCLOCKWISE)
        cv2.imwrite("r4.png", r4)
        r3 = cv2.rotate(r3, cv2.ROTATE_90_COUNTERCLOCKWISE)
        cv2.imwrite("r3.png", r3)


    def convertQImageToMat(self,incomingImage):
        '''  Converts a QImage into an opencv MAT format  '''
        incomingImage = incomingImage.convertToFormat(4)
        width = incomingImage.width()
        height = incomingImage.height()
        ptr = incomingImage.bits()
        ptr.setsize(incomingImage.byteCount())
        arr = np.array(ptr).reshape(height, width, 4)  #  Copies the data
        return arr

    def showSettings(self):
        self.settingsBox.setVisible(not self.settingsBox.isVisible())
        if self.settingsBox.isVisible():
            self.setFixedWidth(594)
            self.setFixedHeight(610)
        else:
            self.setFixedWidth(594)
            self.setFixedHeight(500)

    def openFile(self):
        fileName = QFileDialog.getOpenFileName(self, "Select and Open Video", "/home")[0]
        self.FName=fileName
        self.bulb1.turn_off()
        self.bulb2.turn_off()
        if fileName != '':
            self.mediaPlayer.setMedia(QMediaContent(QUrl.fromLocalFile(fileName)))
            self.statusBar.showMessage(fileName)
            self.playbutton.setEnabled(True)
            self.volumeSlider.setValue(self.mediaPlayer.volume())

    def playclick(self):
        self.mediaPlayer.play()
        self.bulb1.turn_on()
        self.bulb2.turn_on()
    
    def pauseclick(self):
        self.mediaPlayer.pause()

    def stopclick(self):
        self.mediaPlayer.stop()
        self.bulb1.turn_off()
        self.bulb2.turn_off()

    def fullscreen(self):
        self.videoWidget.setFullScreen(True)

    def mouseDoubleClickEvent(self, event):
        self.videoWidget.setFullScreen(not self.videoWidget.isFullScreen())
        event.accept()

    def positionChanged(self, position):
        self.progressSlider.setValue(position)

    def durationChanged(self, duration):
        self.progressSlider.setRange(0, duration)

    def volumeChanged(self, volume):
        self.volumeSlider.setValue(volume)

    def setPosition(self, position):
        self.mediaPlayer.setPosition(position)
        if position==self.mediaPlayer.duration:
            self.bulb1.turn_off()
            self.bulb2.turn_off()

    def setVolume(self, volume):
        self.mediaPlayer.setVolume(volume)

    def setPrev(self,position):
        self.mediaPlayer.setPosition(self.mediaPlayer.position()-1000)

    def setNext(self,position):
        self.mediaPlayer.setPosition(self.mediaPlayer.position()+1000)

    def setFirst(self):
        self.mediaPlayer.setPosition(0)
        self.bulb1.turn_on()
        self.bulb2.turn_on()

    def setLast(self, duration):
        self.mediaPlayer.setPosition(self.mediaPlayer.duration())
        self.bulb1.turn_off()
        self.bulb2.turn_off()
    
    def exitFun(self):
        self.bulb1.turn_off()
        self.bulb2.turn_off()
        sys.exit(app.exec_())

    def discoverBulbs(self):#Burada liste boş geliyor. Bakılacak
        bulbs = discover_bulbs()
        print(bulbs)
    
    def lampCheckFun(self,ip):
        bulb = Bulb(ip, effect="smooth")
        try:
            try:
                bulb.stop_music()
            except:
                pass
            time.sleep(1)
            bulb.start_music(20000)
            bulb.turn_on()
            time.sleep(1)
            bulb.turn_off()
            time.sleep(1)
            bulb.set_rgb(230,30,20)
            bulb.turn_on()
            return True
        except:
            return False

    def testLamp(self):
        if self.LeftTopBox.isChecked():
            st1=self.lampCheckFun(self.LeftTopIpEdit.text())
            if st1:
                self.LeftTopLamp.setEnabled(True)
            else:
                self.LeftTopLamp.setEnabled(False)

        if self.RightTopBox.isChecked():
            st2=self.lampCheckFun(self.RightTopIpEdit.text())
            if st2:
                self.RightTopLamp.setEnabled(True)
            else:
                self.RightTopLamp.setEnabled(False)

        if self.LeftBottomBox.isChecked():
            st3=self.lampCheckFun(self.LeftBottomIpEdit.text())
            if st3:
                self.LeftBottomLamp.setEnabled(True)
            else:
                self.LeftBottomLamp.setEnabled(False)

        if self.RightBottomBox.isChecked():
            st4=self.lampCheckFun(self.RightBottomIpEdit.text())
            if st4:
                self.RightBottomLamp.setEnabled(True)
            else:
                self.RightBottomLamp.setEnabled(False)

    def saveSettings(self):
        settingObject = ConfigParser()
        settingObject["LEFTTOP"] = {
        "checked": self.LeftTopBox.isChecked(),
        "ip": self.LeftTopIpEdit.text()
        }

        settingObject["LEFTBOTTOM"] = {
        "checked": self.LeftBottomBox.isChecked(),
        "ip": self.LeftBottomIpEdit.text()
        }

        settingObject["RIGHTTOP"] = {
        "checked": self.RightTopBox.isChecked(),
        "ip": self.RightTopIpEdit.text()
        }

        settingObject["RIGHTBOTTOM"] = {
        "checked": self.RightBottomBox.isChecked(),
        "ip": self.RightBottomIpEdit.text()
        }

        with open('settings.ini', 'w') as set:
            settingObject.write(set)
        
        self.statusBar.showMessage("Settings are saved")

if __name__ == '__main__':

    def except_hook(cls, exception, traceback):
        sys.__excepthook__(cls, exception, traceback)
    if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
        PyQt5.QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
        PyQt5.QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    sys.excepthook = except_hook
    mainWindow = AL_Player()
    sys.exit(app.exec_())
