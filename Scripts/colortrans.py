# thoughts towards NCGMP09 color translation

import wpgdict

c = ','

def hsv2wpg(hsv):
    cmy = hsv2cmy(hsv)
    wpg = cmy2wpg(cmy)
    return wpg

def wpg2hsv(wpg,hsv):
    oldV = hsv.split(c)[2]
    #cmy = wpg2cmy(wpg)
    #newHsv = cmy2hsv(cmy)
    newHsv = wpgdict.wpgcmykgdict[int(wpg)][1]
    if float(oldV) > float(newHsv.split(c)[2]):
        # replace newV with oldV
        newHsv = newHsv.split(c)[0]+c+newHsv.split(c)[1]+c+oldV
    return newHsv

def wpg2rgb(wpg):
    rgb = wpgdict.wpgcmykgdict[int(wpg)][0]
    return rgb

def __rgb2h(r, g, b):
    var_max = max(r,g,b)
    var_min = min(r,g,b)
    if var_max == var_min:
        return 0.0
    elif var_max == r:
        return (60.0 * ((g - b) / (var_max - var_min)) + 360) % 360.0
    elif var_max == g:
        return 60.0 * ((b - r) / (var_max - var_min)) + 120
    elif var_max == b:
        return 60.0 * ((r - g) / (var_max - var_min)) + 240.0

def cmy2hsv(cmy):
    C = float(cmy.split(c)[0]) / 100.0
    M = float(cmy.split(c)[1]) / 100.0
    Y = float(cmy.split(c)[2]) / 100.0
    r = 1 - C
    g = 1 - M
    b = 1 - Y 
    var_max = max(r,g,b)
    var_min = min(r,g,b)
    var_H = __rgb2h(r,g,b)
    if var_max == 0:
        var_S = 0
    else:
        var_S = 1.0 - (var_min / var_max)       
    var_V = var_max
    h = int(var_H)
    s = int(var_S * 100.0)
    v = int(var_V * 100.0)
    return str(h)+c+str(s)+c+str(v)


def hsv2cmy(hsv):
    # H values are in degrees and are 0 to 360
    # S values are 0..100
    # V values are 0..100
    c = ','
    H = float(hsv.split(c)[0])
    S0 = float(hsv.split(c)[1])
    V0 = float(hsv.split(c)[2])
    if V0 > 100.0:
        V0 = 100.0
    S = S0 / 100.0
    V = V0 / 100.0
    h_floored = int(H)
    h_sub_i = int(h_floored / 60) % 6
    var_f = (H / 60.0) - (h_floored / 60)
    var_p = V * (1.0 - S)
    var_q = V * (1.0 - var_f * S)
    var_t = V * (1.0 - (1.0 - var_f) * S)
       
    if h_sub_i == 0:
        r = V
        g = var_t
        b = var_p
    elif h_sub_i == 1:
        r = var_q
        g = V
        b = var_p
    elif h_sub_i == 2:
        r = var_p
        g = V
        b = var_t
    elif h_sub_i == 3:
        r = var_p
        g = var_q
        b = V
    elif h_sub_i == 4:
        r = var_t
        g = var_p
        b = V
    elif h_sub_i == 5:
        r = V
        g = var_p
        b = var_q
    C = (1.0 - r) * 100
    M = (1.0 - g) * 100
    Y = (1.0 - b) * 100
    cmy = str(int(C))+c+str(int(M))+c+str(int(Y))
    return cmy

def __bin(x):
    # returns nearest preferred color value
    # (0,8,13,20,30,40,50,60,70,100)
    if x <=4:     # x ~ 0
        return 0
    elif x <= 10: # x ~ 8
        return 1
    elif x <= 17: # x ~ 13
        return 2
    elif x <= 25: # x ~ 20
        return 3
    elif x <= 35: # x ~ 30
        return 4
    elif x <= 45: # x ~ 40
        return 5
    elif x <= 55: # x ~ 50
        return 6
    elif x <= 65: # x ~ 60
        return 7
    elif x <= 84: # x ~ 70
        return 8
    else: # x ~ 100
        return 9

def cmy2wpg(cmy):
    C = int(cmy.split(c)[0])
    M = int(cmy.split(c)[1])
    Y = int(cmy.split(c)[2])
    wpg = 100 * __bin(C) + 10 * __bin(Y) + __bin(M)
    return str(wpg)

def wpg2cmy(wpg):
    valdict = {'0':0,'1':8,'2':13,'3':20,'4':30,'5':40,'6':50,'7':60,'8':70,'9':100}
    C = valdict[wpg[0]]
    M = valdict[wpg[2]]
    Y = valdict[wpg[1]]
    cmy = str(C)+c+str(M)+c+str(Y)
    return cmy


#print '%03d' % int(27)

    
