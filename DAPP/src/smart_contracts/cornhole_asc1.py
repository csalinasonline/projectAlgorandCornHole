from pyteal import *


class AppVariables:
    """
    All the variables available in the global state of the application.
    """
    PlayerXState = Bytes("PlayerXState")
    PlayerOState = Bytes("PlayerOState")

    PlayerOAddress = Bytes("PlayerOAddress")
    PlayerXAddress = Bytes("PlayerXAddress")
    PlayerTurnAddress = Bytes("PlayerTurnAddress")
    FundsEscrowAddress = Bytes("FundsEscrowAddress")

    BetAmount = Bytes("BetAmount")
    ActionTimeout = Bytes("ActionTimeout")
    GameStatus = Bytes("GameState")

    @classmethod
    def number_of_int(cls):
        return 5

    @classmethod
    def number_of_str(cls):
        return 4

WIN_PTS = 3

class DefaultValues:
    """
    The default values for the global variables initialized on the transaction that creates the application.
    """
    PlayerXState = Int(0)
    PlayerOState = Int(0)
    GameStatus = Int(0)
    BetAmount = Int(1000000)
    GameDurationInSeconds = Int(3600)


class AppActions:
    """
    Available actions in the CornHole application.
    """
    SetupPlayers = Bytes("SetupPlayers")
    ActionMove = Bytes("ActionMove")
    MoneyRefund = Bytes("MoneyRefund")


def application_start():
    """
    This function represents the start of the application. Here we decide which action will be executed in the current
    application call. If we are creating the application for the very first time we are going to initialize some
    of the global values with their appropriate default values.
    """
    is_app_initialization = Txn.application_id() == Int(0)

    actions = Cond(
        [Txn.application_args[0] == AppActions.SetupPlayers, initialize_players_logic()],
        [And(Txn.application_args[0] == AppActions.ActionMove,
             Global.group_size() == Int(1)), play_action_logic()],
        [Txn.application_args[0] == AppActions.MoneyRefund, money_refund_logic()]
    )

    return If(is_app_initialization, app_initialization_logic(), actions)


def app_initialization_logic():
    """
    Initialization of the default global variables.
    """
    return Seq([
        App.globalPut(AppVariables.PlayerXState, DefaultValues.PlayerXState),
        App.globalPut(AppVariables.PlayerOState, DefaultValues.PlayerOState),
        App.globalPut(AppVariables.GameStatus, DefaultValues.GameStatus),
        App.globalPut(AppVariables.BetAmount, DefaultValues.BetAmount),
        Return(Int(1))
    ])


def initialize_players_logic():
    """
    This function initializes all the other global variables. The end of the execution of this function defines the game
    start. We expect that this logic is performed within an Atomic Transfer of 3 transactions:
    1. Application Call with the appropriate application action argument.
    2. Payment transaction from Player X that funds the Escrow account. The address of this sender is represents the
    PlayerX address.
    3. Payment transaction from Player O that funds the Escrow account. The address of this sender is represents the
    PlayerO address.
    :return:
    """
    player_x_address = App.globalGetEx(Int(0), AppVariables.PlayerXAddress)
    player_o_address = App.globalGetEx(Int(0), AppVariables.PlayerOAddress)

    setup_failed = Seq([
        Return(Int(0))
    ])

    setup_players = Seq([
        Assert(Gtxn[1].type_enum() == TxnType.Payment),
        Assert(Gtxn[2].type_enum() == TxnType.Payment),
        Assert(Gtxn[1].receiver() == Gtxn[2].receiver()),
        Assert(Gtxn[1].amount() == App.globalGet(AppVariables.BetAmount)),
        Assert(Gtxn[2].amount() == App.globalGet(AppVariables.BetAmount)),
        App.globalPut(AppVariables.PlayerXAddress, Gtxn[1].sender()),
        App.globalPut(AppVariables.PlayerOAddress, Gtxn[2].sender()),
        App.globalPut(AppVariables.PlayerTurnAddress, Gtxn[1].sender()),
        App.globalPut(AppVariables.FundsEscrowAddress, Gtxn[1].receiver()),
        App.globalPut(AppVariables.ActionTimeout, Global.latest_timestamp() + DefaultValues.GameDurationInSeconds),
        Return(Int(1))
    ])

    return Seq([
        player_x_address,
        player_o_address,
        If(Or(player_x_address.hasValue(), player_o_address.hasValue()), setup_failed, setup_players)
    ])


def has_player_won(state):
    """
    Checks whether the passed state as an argument is a winning state. There are 8 possible winning states in which
    a specific pattern of bits needs to be activated.
    :param state:
    :return:
    """
    return If(state >= Int(WIN_PTS), Int(1), Int(0))


def play_action_logic():
    """
    Executes an action for the current player in the game and accordingly updates the state of the game. The action
    is passed as an argument to the application call.
    :return:
    """

    player = Txn.application_args[0]
    point = Btoi(Txn.application_args[1])

    state_x = App.globalGet(AppVariables.PlayerXState)
    state_o = App.globalGet(AppVariables.PlayerOState)

    player_x_move = Seq([
        App.globalPut(AppVariables.PlayerXState, Add(state_x, point)),

        If(has_player_won(App.globalGet(AppVariables.PlayerXState)),
           App.globalPut(AppVariables.GameStatus, Int(1))),

        App.globalPut(AppVariables.PlayerTurnAddress, App.globalGet(AppVariables.PlayerOAddress)),
    ])

    player_o_move = Seq([
        App.globalPut(AppVariables.PlayerOState, Add(state_o, point)),

        If(has_player_won(App.globalGet(AppVariables.PlayerOState)),
           App.globalPut(AppVariables.GameStatus, Int(2))),

        App.globalPut(AppVariables.PlayerTurnAddress, App.globalGet(AppVariables.PlayerXAddress)),
    ])

    return Seq([
        Assert(point >= Int(0)),
        Assert(point <= Int(WIN_PTS)),
        Assert(Global.latest_timestamp() <= App.globalGet(AppVariables.ActionTimeout)),
        Assert(App.globalGet(AppVariables.GameStatus) == DefaultValues.GameStatus),
        Assert(Txn.sender() == App.globalGet(AppVariables.PlayerTurnAddress)),
        Assert(And(If(state_x < Int(WIN_PTS), Int(1), Int(0)),
                   If(state_o < Int(WIN_PTS), Int(1), Int(0)))),
        Cond(
            [Txn.sender() == App.globalGet(AppVariables.PlayerXAddress), player_x_move],
            [Txn.sender() == App.globalGet(AppVariables.PlayerOAddress), player_o_move],
        ),
        Return(Int(1))
    ])


def money_refund_logic():
    """
    This function handles the logic for refunding the money in case of a winner, timeout termination. If the
    player whose turn it is hasn't made a move for the predefined period of time, the other player is declared as a
    winner and can withdraw the money.
    This action logic should be performed using an Atomic Transfer of 2 transactions in case of a winner.
    If there is a winner the Atomic Transfer should have the following 2 transactions:
    1. Application Call with the appropriate application action argument.
    2. Payment from the Escrow to the Winner Address with a amount equal to the 2 * BetAmount.
    :return:
    """
    has_x_won_by_playing = App.globalGet(AppVariables.GameStatus) == Int(1)
    has_o_won_by_playing = App.globalGet(AppVariables.GameStatus) == Int(2)

    has_x_won_by_timeout = And(App.globalGet(AppVariables.GameStatus) == Int(0),
                               Global.latest_timestamp() > App.globalGet(AppVariables.ActionTimeout),
                               App.globalGet(AppVariables.PlayerTurnAddress) == App.globalGet(
                                   AppVariables.PlayerOAddress))

    has_o_won_by_timeout = And(App.globalGet(AppVariables.GameStatus) == Int(0),
                               Global.latest_timestamp() > App.globalGet(AppVariables.ActionTimeout),
                               App.globalGet(AppVariables.PlayerTurnAddress) == App.globalGet(
                                   AppVariables.PlayerXAddress))

    has_x_won = Or(has_x_won_by_playing, has_x_won_by_timeout)
    has_o_won = Or(has_o_won_by_playing, has_o_won_by_timeout)

    x_withdraw = Seq([
        Assert(Gtxn[1].receiver() == App.globalGet(AppVariables.PlayerXAddress)),
        Assert(Gtxn[1].amount() == Int(2) * App.globalGet(AppVariables.BetAmount)),
        App.globalPut(AppVariables.GameStatus, Int(1))
    ])

    o_withdraw = Seq([
        Assert(Gtxn[1].receiver() == App.globalGet(AppVariables.PlayerOAddress)),
        Assert(Gtxn[1].amount() == Int(2) * App.globalGet(AppVariables.BetAmount)),
        App.globalPut(AppVariables.GameStatus, Int(2))
    ])

    return Seq([
        Assert(Gtxn[1].type_enum() == TxnType.Payment),
        Assert(Gtxn[1].sender() == App.globalGet(AppVariables.FundsEscrowAddress)),
        Cond(
            [has_x_won, x_withdraw],
            [has_o_won, o_withdraw]
        ),
        Return(Int(1))
    ])


def approval_program():
    return application_start()


def clear_program():
    return Return(Int(1))
