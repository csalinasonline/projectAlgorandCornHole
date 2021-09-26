import streamlit as st
from src.blockchain_utils.credentials import get_client, get_account_credentials, get_indexer
from src.services.game_engine_service import GameEngineService
from playsound import playsound
import algosdk
import sys
import glob
import serial
import time
import serial.tools.list_ports


# methods to access blockchain
client = get_client()
indexer = get_indexer()

# hardcode it for now, these are testnet accounts so we dont care

# this account must have algo in it.  Also DAPP is locked to 10 so need to refresh after 10 runs.
acc_pk = ' '
acc_address = ' '

# player 'X' and 'O' info, public an private on TestNet
player_x_pk = ' '
player_x_address = ' '
player_o_pk = ' '
player_o_address = ' '

# save a list of serial device
devices = list()


# Streamlit state variables defined here
if "game_local_finished" not in st.session_state:
    st.session_state.game_local_finished = False

if "player_x_local_score" not in st.session_state:
    st.session_state.player_x_local_score = 0
    
if "player_o_local_score" not in st.session_state:
    st.session_state.player_o_local_score = 0    

if "player_x_flag" not in st.session_state:
    st.session_state.player_x_flag = False

if "player_o_flag" not in st.session_state:
    st.session_state.player_o_flag = False
    
if "players_reg_flag" not in st.session_state:
    st.session_state.players_reg_flag = False

if "local_log" not in st.session_state:
    st.session_state.local_log = []

if "submitted_transactions" not in st.session_state:
    st.session_state.submitted_transactions = []

if "player_turn" not in st.session_state:
    st.session_state.player_turn = "X"

if "game_state" not in st.session_state:
    st.session_state.game_state = ['-'] * 9

if "x_state" not in st.session_state:
    st.session_state.x_state = 0

if "o_state" not in st.session_state:
    st.session_state.o_state = 0

if "game_state" not in st.session_state:
    st.session_state.game_state = ['-'] * 9
    
if "game_status" not in st.session_state:
    st.session_state.game_status = 0

if "is_app_deployed" not in st.session_state:
    st.session_state.is_app_deployed = False

if "is_game_started" not in st.session_state:
    st.session_state.is_game_started = False

if "game_engine" not in st.session_state:
    st.session_state.game_engine = GameEngineService(app_creator_pk=acc_pk,
                                                    app_creator_address=acc_address,
                                                    player_x_pk=player_x_pk,
                                                    player_x_address=player_x_address,
                                                    player_o_pk=player_o_pk,
                                                    player_o_address=player_o_address)

# display public accounts for both players
st.title("Addresses")
st.write(f"app_creator: {acc_address}")
st.write(f"player_x: {player_x_address}")
st.write(f"player_o: {player_o_address}")
st.write("You need to fund those accounts on the following link: https://bank.testnet.algorand.network/")

# Step 1: App deployment ===
st.title("Step 1: App deployment")
st.write("In this step we deploy the CornHole Stateful Smart Contract to the Algorand TestNetwork")

# deploy it if not, else doh it
def deploy_application():
    if st.session_state.is_app_deployed:
        return

    app_deployment_txn_log = st.session_state.game_engine.deploy_application(client)
    st.session_state.submitted_transactions.append(app_deployment_txn_log)
    st.session_state.is_app_deployed = True

# add button to deploy app
if st.session_state.is_app_deployed:
    st.success(f"The app is deployed on TestNet with the following app_id: {st.session_state.game_engine.app_id}")
else:
    st.error(f"The app is not deployed! Press the button below to deploy the application.")
    _ = st.button("Deploy App", on_click=deploy_application)

# Step 2: Start of the game ===
st.title("Step 2: Mark the start of the game")
st.write("Ensure CornHole Devices are avaliable")

#
list_ports = list(serial.tools.list_ports.comports())
if len(list_ports) < 4:
    st.write("Found All Devices")
    for idx, item in enumerate(list_ports):
        items = str(item).split()
        devices.append(items[0])
        st.write(items[0])
        

# start game logic method
def start_game():
    if st.session_state.is_game_started:
        return

    start_game_txn_log = st.session_state.game_engine.start_game(client)
    st.session_state.submitted_transactions.append(start_game_txn_log)
    st.session_state.is_game_started = True

# add start button
if st.session_state.is_game_started:
    st.success("The game has started")
else:
    st.error(f"The game has not started! Press the button below to start the game.")
    _ = st.button("Start game", on_click=start_game)
    
# Step 3: Execute game ===   
st.title("Step 3: Execute game actions")

# get game stat via algo indexer method
def get_game_status(indexer, app_id):
    response = indexer.search_applications(application_id=app_id)
    game_status_key = "R2FtZVN0YXRl"

    for global_variable in response['applications'][0]['params']['global-state']:
        if global_variable['key'] == game_status_key:
            return global_variable['value']['uint']


# via game status on blockchain save to local status 
def check_game_status():
    if st.session_state.is_game_started:
        game_status = get_game_status(indexer, app_id=st.session_state.game_engine.app_id)
        st.session_state.game_status = game_status

# TODO
# Add support for QR Code scanning and player registration
def reg_action():

    # get all serial devices on network
    list_dev = list()
    for dev in devices:
        list_dev.append(serial.Serial(dev,\
            baudrate=9600,\
            parity=serial.PARITY_NONE,\
            stopbits=serial.STOPBITS_ONE,\
            bytesize=serial.EIGHTBITS,\
            timeout=None))

    # poll all devices specificall the QR code machines
    flag_reg = True
    while flag_reg:
        
        # loop thru devices
        for _dev in list_dev:
        
             # if existing serial close it
            if _dev.isOpen():
                _dev.close()
            
            # open new serial
            _dev.open()

            # get response
            resp = _dev.readline().decode("utf-8")

            # parse response and register players
            if resp:
                resps = resp.split(',')
                if len(resps) >= 3:
                    try:  # needed to catch issues with some strings
                        if len(resps[0]) > 0 and len(resps[1]) > 0 and len(resps[2]) > 0 and len(resps[3]) > 0:
                            node_type = resps[0]
                            player = resps[1]
                            tick = resps[2]
                            addr = resps[3]
                            if 'QR' in node_type:
                                if 'X' in player and not st.session_state.player_x_flag:
                                    st.session_state.player_x_flag = True
                                    st.session_state.local_log.append('Player X: ' + addr + ' Registered')
                                    st.write('Player X: ' + addr + ' Registered')
                                if 'O' in player and not st.session_state.player_o_flag:
                                    st.session_state.player_o_flag = True
                                    st.session_state.local_log.append('Player O: ' + addr + ' Registered')
                                    st.write('Player O: ' + payload + ' Registered')

                                #st.write(resp)
                    except:
                        pass
                           
            # if both player registered flag it                    
            if st.session_state.player_x_flag and st.session_state.player_o_flag and not st.session_state.players_reg_flag:
                st.session_state.players_reg_flag = True
                st.session_state.local_log.append('Both Players Registered')
                st.write('Both Players Registered')
                flag_reg = False

            _dev.close()


# where all the action happens            
def play_action(action_idx):
        
        # get all serial devices on network
        list_dev = list()
        for dev in devices:
            list_dev.append(serial.Serial(dev,\
                baudrate=9600,\
                parity=serial.PARITY_NONE,\
                stopbits=serial.STOPBITS_ONE,\
                bytesize=serial.EIGHTBITS,\
                timeout=None))

        # poll all devices specificall the QR code machines
        flag_reg = True
        while flag_reg:
            
            # loop thru devices
            for _dev in list_dev:
            
                 # if existing serial close it
                if _dev.isOpen():
                    _dev.close()
                
                # open new serial
                _dev.open()

                # get response
                resp = _dev.readline().decode("utf-8")
                #st.write(resp)

                # parse response and register players
                if resp:
                
                    # split our csv string
                    resps = resp.split(',')
                    
                    # ensure enough parameters?
                    if len(resps) >= 3:
                        try:  # needed to catch issues with some broken strings, so try?
                            if len(resps[0]) > 0 and len(resps[1]) > 0 and len(resps[2]) > 0 and len(resps[3]) > 0:
                                
                                # string good so parse in info
                                node_type = resps[0]
                                player = resps[1]
                                tick = resps[2]
                                score = resps[3]
                                
                                # based on node type and player start play action
                                instant_score = 0
                                if 'BRD' in node_type:
                                
                                    # player 'X' is up
                                    if 'X' in player:
                                    
                                        # make sure serial determines player turn and log it
                                        st.session_state.player_turn == "X"
                                        st.session_state.local_log.append('Player X Scored: ' + score)
                                                                                
                                        # convert to intermediate scoring
                                        if int(score) == 1:
                                            st.session_state.player_x_local_score = st.session_state.player_x_local_score + 1
                                            instant_score = 1
                                        if int(score) == 3:
                                            st.session_state.player_x_local_score = st.session_state.player_x_local_score + 3
                                            instant_score = 3                                          
                                    
                                    # player 'O' is up
                                    if 'O' in player:
                                    
                                        # ...
                                        st.session_state.player_turn == "O" 
                                        st.session_state.local_log.append('Player O Scored: ' + score)
                                        
                                        # ...
                                        if int(score) == 1:
                                            st.session_state.player_o_local_score = st.session_state.player_o_local_score + 1
                                            instant_score = 1
                                        if int(score) == 3:
                                            st.session_state.player_o_local_score = st.session_state.player_o_local_score + 3
                                            instant_score = 3

                                    # blockchain interaction here
                                    try:  # try to send something to blockchain
                                        play_action_txn = st.session_state.game_engine.play_action(client,
                                                                                                   player_id=st.session_state.player_turn,
                                                                                                   action_position=instant_score)
                                    except:  # tx failed?
                                        st.session_state.submitted_transactions.append(f"Rejected transaction. Tried to put "
                                                                                       f"{st.session_state.player_turn} scored {instant_score}")
                                        return          
                                    
                                    # save tx info
                                    st.session_state.submitted_transactions.append(play_action_txn)
                                    
                                    # save local state info and swap players
                                    if st.session_state.player_turn == "X":
                                        
                                        # ...
                                        st.session_state.x_state = instant_score + st.session_state.x_state
                                        st.session_state.player_turn = "O"
                                    else:
                                    
                                        #
                                        st.session_state.o_state = instant_score + st.session_state.o_state
                                        st.session_state.player_turn = "X"                                        

                                    # need to delay here!
                                    time.sleep(10)
                                    
                                    # then check game status on blockchain
                                    check_game_status()
                                    
                                    # alert we done and next turn player
                                    playsound('turn.mp3')

                        except:  # if we err out just pass
                            pass
                               
                # player won by pt threshold, then kick out gracefully                    
                if st.session_state.player_o_local_score >= 3 or st.session_state.player_x_local_score >= 3 and not st.session_state.game_local_finished:
                    st.session_state.game_local_finished = True
                    st.session_state.local_log.append('Game Finished')
                    flag_reg = False
                    _dev.close() 
                    break

                # yep we got here and we must close
                _dev.close()        

# TODO 
# add registration button for scanning QR codes
#_ = st.button("Register to Play CornHole", on_click=reg_action)                   

# add button to start play actions              
_ = st.button('Play CornHole', on_click=play_action,
              args=(0,))              

# show current pts
st.title("Game Points: ")
st.write(f"x_state: {st.session_state.x_state}")
st.write(f"o_state: {st.session_state.o_state}")

# Step 4: Withdraw funds ===


# winner get his/her money
def withdraw_funds(winner):
    if winner is None:
        try:
            fund_escrow_txn = st.session_state.game_engine.fund_escrow(client=client)
            st.session_state.submitted_transactions.append(fund_escrow_txn)

            st.session_state.submitted_transactions.append(txn_description)
        except:
            st.session_state.submitted_transactions.append("Rejected transaction. Unsuccessful withdrawal.")
    else:
        try:
            fund_escrow_txn = st.session_state.game_engine.fund_escrow(client=client)
            st.session_state.submitted_transactions.append(fund_escrow_txn)

            txn_description = st.session_state.game_engine.win_money_refund(client, player_id=winner)
            st.session_state.submitted_transactions.append(txn_description)
        except:
            st.session_state.submitted_transactions.append("Rejected transaction. Unsuccessful withdrawal.")

# go here every refresh and check winner
if st.session_state.game_status == 0:

    # game still going on...
    st.write("The game is still active.")

else:

    # we have winner
    winner = None
    if st.session_state.game_status == 1:
        st.balloons()
        playsound('win.mp3')
        st.success("Player X won the game.")
        winner = "X"
    elif st.session_state.game_status == 2:
        st.balloons()
        playsound('win.mp3')
        st.success("Player O won the game.")
        winner = "O"
    
    # need some delay!
    time.sleep(5)
    
    # call method for delegating money
    withdraw_funds(winner)
    
    
# Step 5: Log it === 
st.title("Submitted transactions")

# log events on blockchain txs  
for txn in st.session_state.submitted_transactions:
    if "Rejected transaction." in txn:
        st.error(txn)
    else:
        st.success(txn)

# log events locally
st.title("Local log")

# ...
for logit in st.session_state.local_log:
    st.success(logit)