from pathlib import Path
from typing import Callable, Optional, Any
import json
import pytest
from web3 import Web3

from client.client import EthAppClient, StatusWord
import client.response_parser as ResponseParser
from client.utils import get_selector_from_data, recover_transaction

from ragger.error import ExceptionRAPDU
from ragger.firmware import Firmware
from ragger.backend import BackendInterface
from ragger.navigator import Navigator, NavInsID

from constants import ABIS_FOLDER


BIP32_PATH = "m/44'/60'/0'/0/0"
NONCE = 21
GAS_PRICE = 13
GAS_LIMIT = 21000
FROM = bytes.fromhex("1122334455667788990011223344556677889900")
TO = bytes.fromhex("0099887766554433221100998877665544332211")
NFTS = [(1, 3), (5, 2), (7, 4)]  # tuples of (token_id, amount)
DATA = "Some data".encode()
DEVICE_ADDR: Optional[bytes] = None


class NFTCollection:
    addr: bytes
    name: str
    chain_id: int

    def __init__(self, addr: bytes, name: str, chain_id: int, contract):
        self.addr = addr
        self.name = name
        self.chain_id = chain_id
        self.contract = contract


class Action:
    fn_name: str
    fn_args: list[Any]
    nav_fn: Callable

    def __init__(self, fn_name: str, fn_args: list[Any], nav_fn: Callable):
        self.fn_name = fn_name
        self.fn_args = fn_args
        self.nav_fn = nav_fn


def common_nav_nft(is_nano: bool,
                   nano_steps: int,
                   stax_steps: int,
                   reject: bool) -> list[NavInsID]:
    moves = []
    if is_nano:
        moves += [NavInsID.RIGHT_CLICK] * nano_steps
        if reject:
            moves += [NavInsID.RIGHT_CLICK]
        moves += [NavInsID.BOTH_CLICK]
    else:
        moves += [NavInsID.USE_CASE_REVIEW_TAP] * stax_steps
        if reject:
            moves += [
                NavInsID.USE_CASE_REVIEW_REJECT,
                NavInsID.USE_CASE_CHOICE_CONFIRM
            ]
        else:
            moves += [NavInsID.USE_CASE_REVIEW_CONFIRM]
    return moves


def snapshot_test_name(nft_type: str, fn: str, chain_id: int, reject: bool) -> str:
    name = f"{nft_type}_{fn}_{str(chain_id)}"
    if reject:
        name += "-rejected"
    return name


def common_test_nft(firmware: Firmware,
                    backend: BackendInterface,
                    navigator: Navigator,
                    default_screenshot_path: Path,
                    collec: NFTCollection,
                    action: Action,
                    reject: bool,
                    plugin_name: str):
    global DEVICE_ADDR
    app_client = EthAppClient(backend)

    if firmware.device == "nanos":
        pytest.skip("Not supported on LNS")

    if DEVICE_ADDR is None:  # to only have to request it once
        with app_client.get_public_addr(display=False):
            pass
        _, DEVICE_ADDR, _ = ResponseParser.pk_addr(app_client.response().data)

    data = collec.contract.encodeABI(action.fn_name, action.fn_args)
    app_client.set_plugin(plugin_name,
                          collec.addr,
                          get_selector_from_data(data),
                          collec.chain_id)
    app_client.provide_nft_metadata(collec.name, collec.addr, collec.chain_id)
    tx_params = {
        "nonce": NONCE,
        "gasPrice": Web3.to_wei(GAS_PRICE, "gwei"),
        "gas": GAS_LIMIT,
        "to": collec.addr,
        "value": 0,
        "chainId": collec.chain_id,
        "data": data,
    }
    with app_client.sign(BIP32_PATH, tx_params):
        navigator.navigate_and_compare(default_screenshot_path,
                                 snapshot_test_name(plugin_name.lower(),
                                                    action.fn_name,
                                                    collec.chain_id,
                                                    reject),
                                 action.nav_fn(firmware.is_nano,
                                               collec.chain_id,
                                               reject))
    # verify signature
    vrs = ResponseParser.signature(app_client.response().data)
    addr = recover_transaction(tx_params, vrs)
    assert addr == DEVICE_ADDR


def common_test_nft_reject(test_fn: Callable,
                           firmware: Firmware,
                           backend: BackendInterface,
                           navigator: Navigator,
                           default_screenshot_path: Path,
                           collec: NFTCollection,
                           action: Action):
    with pytest.raises(ExceptionRAPDU) as e:
        test_fn(firmware, backend, navigator, default_screenshot_path, collec, action, True)
    assert e.value.status == StatusWord.CONDITION_NOT_SATISFIED

# ERC-721


ERC721_PLUGIN = "ERC721"

with open(f"{ABIS_FOLDER}/erc721.json", encoding="utf-8") as file:
    contract_erc721 = Web3().eth.contract(
        abi=json.load(file),
        address=bytes(20)
    )

# ui navigator functions

def nav_erc721_transfer_from(is_nano: bool,
                             chain_id: int,
                             reject: bool) -> list[NavInsID]:
    nano_steps = 7
    stax_steps = 3
    if chain_id != 1:
        nano_steps += 1
        stax_steps += 1
    return common_nav_nft(is_nano, nano_steps, stax_steps, reject)


def nav_erc721_approve(is_nano: bool,
                       chain_id: int,
                       reject: bool) -> list[NavInsID]:
    nano_steps = 7
    stax_steps = 3
    if chain_id != 1:
        nano_steps += 1
        stax_steps += 1
    return common_nav_nft(is_nano, nano_steps, stax_steps, reject)


def nav_erc721_set_approval_for_all(is_nano: bool,
                                    chain_id: int,
                                    reject: bool) -> list[NavInsID]:
    nano_steps = 6
    if chain_id != 1:
        nano_steps += 1
    return common_nav_nft(is_nano, nano_steps, 3, reject)


collecs_721 = [
    NFTCollection(bytes.fromhex("bc4ca0eda7647a8ab7c2061c2e118a18a936f13d"),
                  "Bored Ape Yacht Club",
                  1,
                  contract_erc721),
    NFTCollection(bytes.fromhex("670fd103b1a08628e9557cd66b87ded841115190"),
                  "y00ts",
                  137,
                  contract_erc721),
    NFTCollection(bytes.fromhex("2909cf13e458a576cdd9aab6bd6617051a92dacf"),
                  "goerlirocks",
                  5,
                  contract_erc721),
]
actions_721 = [
    Action("safeTransferFrom",
           [FROM, TO, NFTS[0][0], DATA],
           nav_erc721_transfer_from),
    Action("safeTransferFrom",
           [FROM, TO, NFTS[0][0]],
           nav_erc721_transfer_from),
    Action("transferFrom",
           [FROM, TO, NFTS[0][0]],
           nav_erc721_transfer_from),
    Action("approve",
           [TO, NFTS[0][0]],
           nav_erc721_approve),
    Action("setApprovalForAll",
           [TO, False],
           nav_erc721_set_approval_for_all),
]


@pytest.fixture(name="collec_721", params=collecs_721)
def collec_721_fixture(request) -> NFTCollection:
    return request.param


@pytest.fixture(name="action_721", params=actions_721)
def action_721_fixture(request) -> Action:
    return request.param


def test_erc721(firmware: Firmware,
                backend: BackendInterface,
                navigator: Navigator,
                default_screenshot_path: Path,
                collec_721: NFTCollection,
                action_721: Action,
                reject: bool = False):
    common_test_nft(firmware,
                    backend,
                    navigator,
                    default_screenshot_path,
                    collec_721,
                    action_721,
                    reject,
                    ERC721_PLUGIN)


def test_erc721_reject(firmware: Firmware,
                       backend: BackendInterface,
                       navigator: Navigator,
                       default_screenshot_path: Path):
    common_test_nft_reject(test_erc721,
                           firmware,
                           backend,
                           navigator,
                           default_screenshot_path,
                           collecs_721[0],
                           actions_721[0])


# ERC-1155

ERC1155_PLUGIN = "ERC1155"

with open(f"{ABIS_FOLDER}/erc1155.json", encoding="utf-8") as file:
    contract_erc1155 = Web3().eth.contract(
        abi=json.load(file),
        address=bytes(20)
    )


# ui navigator functions

def nav_erc1155_safe_transfer_from(is_nano: bool,
                                   chain_id: int,
                                   reject: bool) -> list:
    nano_steps = 8
    if chain_id != 1:
        nano_steps += 1
    return common_nav_nft(is_nano, nano_steps, 4, reject)


def nav_erc1155_safe_batch_transfer_from(is_nano: bool,
                                         chain_id: int,
                                         reject: bool) -> list:
    nano_steps = 7
    stax_steps = 3
    if chain_id != 1:
        nano_steps += 1
        stax_steps += 1
    return common_nav_nft(is_nano, nano_steps, stax_steps, reject)


def nav_erc1155_set_approval_for_all(is_nano: bool,
                                     chain_id: int,
                                     reject: bool) -> list:
    nano_steps = 6
    if chain_id != 1:
        nano_steps += 1
    return common_nav_nft(is_nano, nano_steps, 3, reject)


collecs_1155 = [
    NFTCollection(bytes.fromhex("495f947276749ce646f68ac8c248420045cb7b5e"),
                  "OpenSea Shared Storefront",
                  1,
                  contract_erc1155),
    NFTCollection(bytes.fromhex("2953399124f0cbb46d2cbacd8a89cf0599974963"),
                  "OpenSea Collections",
                  137,
                  contract_erc1155),
    NFTCollection(bytes.fromhex("f4910c763ed4e47a585e2d34baa9a4b611ae448c"),
                  "OpenSea Collections",
                  5,
                  contract_erc1155),
]
actions_1155 = [
    Action("safeTransferFrom",
           [FROM, TO, NFTS[0][0], NFTS[0][1], DATA],
           nav_erc1155_safe_transfer_from),
    Action("safeBatchTransferFrom",
           [
               FROM,
               TO,
               list(map(lambda nft: nft[0], NFTS)),
               list(map(lambda nft: nft[1], NFTS)),
               DATA
           ],
           nav_erc1155_safe_batch_transfer_from),
    Action("setApprovalForAll",
           [TO, False],
           nav_erc1155_set_approval_for_all),
]


@pytest.fixture(name="collec_1155", params=collecs_1155)
def collec_1155_fixture(request) -> bool:
    return request.param


@pytest.fixture(name="action_1155", params=actions_1155)
def action_1155_fixture(request) -> Action:
    return request.param


def test_erc1155(firmware: Firmware,
                 backend: BackendInterface,
                 navigator: Navigator,
                 default_screenshot_path: Path,
                 collec_1155: NFTCollection,
                 action_1155: Action,
                 reject: bool = False):
    common_test_nft(firmware,
                    backend,
                    navigator,
                    default_screenshot_path,
                    collec_1155,
                    action_1155,
                    reject,
                    ERC1155_PLUGIN)


def test_erc1155_reject(firmware: Firmware,
                        backend: BackendInterface,
                        navigator: Navigator,
                        default_screenshot_path: Path):
    common_test_nft_reject(test_erc1155,
                           firmware,
                           backend,
                           navigator,
                           default_screenshot_path,
                           collecs_1155[0],
                           actions_1155[0])
