#import files
#from functions import *
import functions as fn

def main(fileDir: str, strings: int, tuning: list) -> None:

    #inizializza var globali    --------------  SERVE???
    NOME_FILE = fileDir
    NUM_CORDE = strings
    ACCORDATURA = tuning
    NUM_TASTI = 19 #<---------------------------------------------------------IMPLEMENTARE NUMERO TASTI!!!
    #OUT_SCORE = ''

    #carica la partitura
    score = fn.leggifile(NOME_FILE)
    if score == '-1':
        return

    #genera matrice tastiera
    fb = fn.fretboard(NUM_CORDE, NUM_TASTI, ACCORDATURA).getMatrix()

    #analizza file e divide in battute e voci
    barObjList, scoreList = fn.makeBarList(score, fb)

    #crea un unico flusso di note
    finalScore = fn.mergeBarList(barObjList)

    #colora le note a seconda della fattibilitÃ 
    #nero = ok  |   arancione = da verificare   |   rosso = non eseguibile
    fn.makeColor(finalScore)  

    #riscrive la parte con i colori aggiunti
    fn.rewriteScore(scoreList, barObjList) 

    #genera file debug lista note
    fn.debugNoteList(finalScore, NOME_FILE)



#test debug
if __name__ == '__main__':
    main('C:\\Users\\stefa\\Desktop\\p.musicxml', 6, ['E4', 'B3', 'G3', 'D3', 'A2', 'E2'])