import requests
from bs4 import BeautifulSoup
from collections import deque
from time import sleep
import win32print
import win32ui
from PIL import Image, ImageWin
from io import StringIO
import tkinter as tk
from tkinter import font
import threading
 
class Application(tk.Frame):
    '''
    The first function that tkinter runs
    Sets up windowReg, a list of Lambda functions that change the content of the window
    Changes into the Entry Window configuration
    '''
    def __init__(self, master=None):
        super().__init__(master) 
        self.master = master
        self.windowReg = {0: lambda:(self.EntryWindow()), 1: lambda:(self.scrapingWindow())}        
        self.pack()
        self.windowReg[0]()

#The initial window. The user enters the hashtag in this window
    def EntryWindow(self):
        self.master.geometry('150x230')
        self.prompt = tk.Label(self, text="Enter Hashtag", font= altFont)
        self.prompt.pack(pady=25)
        self.tagEntry = tk.Entry(self)
        self.tagEntry.pack(pady =10)
        self.Advance = tk.Button(self, text="Validate", fg="green", command=lambda: self.authenticateTag(self.tagEntry.get()))
        self.Advance.pack(pady= 15)
        self.quitButton = tk.Button(self, text="QUIT", fg="red", command=self.master.destroy)
        self.quitButton.pack(pady =5)
#The change to the main window after the tag is checked
    def authenticateTag(self, tag):
        print('Attempting ' + tag)
        if tag != "" and len(tag.split(' ')) < 2:
            self.tag = tag
            self.ChangeWindow(1)
        else:
            self.prompt['fg'] = 'red'

#The window which shows how many photos are yet to be printed
    def scrapingWindow(self):
        self.master.geometry('500x500')
        self.hashtagLabel = tk.Label(self, text="#" + self.tag, font=mainFont)
        self.hashtagLabel.pack(pady= 100)
        self.queueLabel = tk.Label(self, text="Give it a second...", font=altFont)
        self.queueLabel.pack(pady= 50)
        self.quitButton = tk.Button(self, text="QUIT", fg="red", command=self.master.destroy)
        self.quitButton.pack()
        '''
        The scraper and printer are both initialized from this function
        printerThread eventually makes its way into the loop in InstaPrinter()
        this happens after initializing scraperThread which loops in InstaScraper()
        '''
        printerThread = threading.Thread(target=Initialize, args=(self.tag,))
        printerThread.start()

#clears widgets, loads configuration as given in windowReg
    def ChangeWindow(self, windowNum):
        for child in self.winfo_children():
            child.destroy()
        self.windowReg[windowNum]()

#changes queueLabel text as photos come in/are printed
    def Increment(self, newVal):
        self.queueLabel['text'] = str(newVal) + ' posts being printed, GET POSTING!'

    def alive(self):
        return True


#Downloads photo and stores it as a PIL Image
def DownloadImageData(_photoURL):
    img = requests.get(_photoURL, stream=True)
    return Image.open(img.raw)
 
'''
Function creates page with downloaded photo and phrase then prints it
'''
def PrintPage(_photoData):
    global phrase
    printer = win32print.GetDefaultPrinter()
    
    #A Device Context is a data structure windows uses to get devices' drawing capabilities, all draw calls are done with device contexts
    #https://docs.microsoft.com/en-us/cpp/mfc/device-contexts?view=vs-2019
    deviceContext = win32ui.CreateDC ()
    deviceContext.CreatePrinterDC (printer)
    
    #GetDeviceCaps is a function used to get the specific capabilities of a device context
    #https://docs.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-getdevicecaps
    PHYSICALWIDTH = 110
    PHYSICALHEIGHT = 111
    docSize = (deviceContext.GetDeviceCaps(PHYSICALWIDTH),deviceContext.GetDeviceCaps(PHYSICALHEIGHT))
    
    #A4 papers are 8.5" x 11", this program runs best with A4 paper
    inchUnit = docSize[1]/11

    #The coordinates of the centers of the photo and label
    #The coordinate system has (0,0) be the top-left of the page
    photoCenter = (docSize[0]/2, docSize[1]/2 - 2*inchUnit)
    labelCenter = (docSize[0]/2, docSize[1]/2 + 2*inchUnit)

    #starts document
    deviceContext.StartDoc('image')
    deviceContext.StartPage()

    #device contexts take Dib draw calls for images
    dib = ImageWin.Dib(_photoData)
    dib.draw(deviceContext.GetHandleOutput (), (int(photoCenter[0] - dib.size[0]), int(photoCenter[1] - dib.size[1]), int(photoCenter[0] + dib.size[0]), int(photoCenter[1] + dib.size[1])))
    deviceContext.DrawText(phrase, (int(0), int(labelCenter[1] - 20), int(docSize[0]), int(labelCenter[1] + 20)))
    
    #The document is then ended and the device context deleted
    #This is what sends this paper to Windows' printer spooler
    deviceContext.EndPage()
    deviceContext.EndDoc()
    deviceContext.DeleteDC()

'''
This function runs on its own thread
As URLs are fed into the queue (photos), they are downloaded and printed
The GUI is updated to reflect this
'''
def InstaPrinter(_tag):
    global phrase
    app.Increment(0)
    phrase = 'HOW #' + _tag.upper() + ' IS THIS?'
    while True:
        try:
            heartbeat = app.alive()
            if len(photos) > 0:
                print(str(len(photos)))
                PrintPage(DownloadImageData(photos.popleft()))
                app.Increment(len(photos))
        except:
            break
    print('killed printer')
'''
The first function in the scraping process
A http get request downloads the html contents 
All photodata is returned in an array of strings
'''
def Scrape(_tag):
    page = requests.get('https://www.instagram.com/explore/tags/' + _tag)
    raw = page.text
    start = raw.find('script type="text/javascript">window._sharedData')
    end = raw.find('"}}]},"edge_hashtag_to_c')
    raw = raw[start + len('script type="text/javascript">window._sharedData = '):end + 5]
    raw = raw.split('edge_media_to_caption')
    raw = raw[1:]
    return raw

'''
Second function in the webscraping proccess
The timestamp and URLs of all photos newer than the last one added to the printer queue are extracted from the list of string photo data
The timestamp of the newest photo is recorded and the URLs of all photos are then all fed to the queue from oldest to newest
'''
def Extract(_photoData):
    global newestPhotoTimestamp
    feed = []
    for blurb in _photoData:
        timestampStart = blurb.find('p":') + 3
        timestamp = blurb[timestampStart: timestampStart + 10]
        timestamp = int(timestamp)
        if timestamp <= newestPhotoTimestamp:
            break
        photoUrl = blurb[blurb.find('display_url":') + len('display_url":') + 1:]
        photoUrl = photoUrl[:photoUrl.find('",')]
        photoUrl = Clean(photoUrl)
        feed.append((timestamp, photoUrl))
    if len(feed) > 0:
        newestPhotoTimestamp = feed[0][0]
        feed.reverse()
        for pic in feed:
            photos.append(pic[1])
        app.Increment(len(photos))

'''
Sometime since August 2019, Instagram replaced all &'s in the urls of all photos to \u0026's
As such following those URLs as is would lead to a dead end
Interestingly, inspecting element of an Instagram Webpage shows the URLs correctly with &'s
Regardless, simply replacing all instances allows for the viewing of photos
'''
def Clean(_url):
    _url = _url.replace('\\u0026','&')
    return _url


 
'''
This function runs on its own thread
Every 5 seconds, the two-part webscraping process happens
'''
def InstaScraper(_tag):
    while True:
        try:
            heartbeat = app.alive()
            Extract(Scrape(_tag))    
            sleep(5)
        except:
            break
    print('killed scraper')

'''
This function happens prior to any webscraping
Records the timestamp of the newest photo for the hashtag
Initializes scraper and printer functionality
'''
def Initialize(tag):
    global newestPhotoTimestamp
    global threadsRunning
    threadsRunning = True
    photoData = Scrape(tag)
    blurb = photoData[0]
    timestampStart = blurb.find('p":') + 3
    timestamp = blurb[timestampStart: timestampStart + 10]
    newestPhotoTimestamp = int(timestamp)
    scraperThread = threading.Thread(target=InstaScraper, args=(tag,))
    scraperThread.start()
    InstaPrinter(tag)



#Global variables
threadsRunning = False 
photos = deque()
phrase = ''
scraperThread = None
printerThread = None
newestPhotoTimestamp = 0

#Starting GUI
root = tk.Tk()
mainFont = tk.font.Font(family='Lucidia Grande', size = 25)
altFont = tk.font.Font(family='Lucidia Grande', size = 15)
app = Application(master=root)
app.mainloop()
threadsRunning = False