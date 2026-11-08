#!/usr/bin/env python3
"""Apply DerenguhGram overlay + minimal audited patches to pinned tdesktop."""
from pathlib import Path
import argparse, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
def patch(path, old, new, count=1):
    p=Path(path); s=p.read_text()
    if s.count(old)!=count: raise SystemExit(f'anchor mismatch in {p} ({s.count(old)}!={count}): {old[:120]!r}')
    p.write_text(s.replace(old,new))
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('target',type=Path); a=ap.parse_args(); t=a.target
    subprocess.run([sys.executable,str(ROOT/'scripts/apply_overlay.py'),str(ROOT/'integrations/desktop'),str(t/'Telegram/SourceFiles')],check=True)
    s=t/'Telegram/SourceFiles'
    # Proxy type
    patch(s/'mtproto/mtproto_proxy_data.h','''		Mtproto,
		Web,
	};''','''		Mtproto,
		Web,
		Derenguh,
	};''')
    patch(s/'mtproto/mtproto_proxy_data.cpp','''	} else if (type == Type::None || host.isEmpty() || !port) {
		return Status::Invalid;
	} else if (type == Type::Mtproto) {''','''	} else if (type == Type::Derenguh) {
		if (host.isEmpty() || !port || user.isEmpty()) return Status::Invalid;
		const auto key = QByteArray::fromBase64(password.toLatin1(), QByteArray::Base64UrlEncoding);
		return key.size() == 16 ? Status::Valid : Status::Invalid;
	} else if (type == Type::None || host.isEmpty() || !port) {
		return Status::Invalid;
	} else if (type == Type::Mtproto) {''')
    patch(s/'mtproto/mtproto_proxy_data.cpp','''	return (type == Type::Socks5 || type == Type::Mtproto)
		&& !qthelp::is_ipv6(host)''','''	return (type == Type::Socks5 || type == Type::Mtproto || type == Type::Derenguh)
		&& !qthelp::is_ipv6(host)''')
    patch(s/'mtproto/mtproto_proxy_data.cpp','''	} else if (proxy.type == ProxyData::Type::Mtproto
		|| proxy.type == ProxyData::Type::Web) {
		return QNetworkProxy::NoProxy;
	}''','''	} else if (proxy.type == ProxyData::Type::Mtproto
		|| proxy.type == ProxyData::Type::Web
		|| proxy.type == ProxyData::Type::Derenguh) {
		return QNetworkProxy::NoProxy;
	}''')
    # serialization
    patch(s/'core/core_settings_proxy.cpp','''		case 4: return MTP::ProxyData::Type::Web;''','''		case 4: return MTP::ProxyData::Type::Web;
		case 5: return MTP::ProxyData::Type::Derenguh;''')
    patch(s/'core/core_settings_proxy.cpp','''			case MTP::ProxyData::Type::Web: return 4;''','''			case MTP::ProxyData::Type::Web: return 4;
			case MTP::ProxyData::Type::Derenguh: return 5;''')
    # transport selection
    patch(s/'mtproto/connection_tcp.cpp','#include "mtproto/details/mtproto_web_proxy_socket.h"','#include "mtproto/details/mtproto_web_proxy_socket.h"\n#include "mtproto/details/mtproto_derenguh_socket.h"')
    patch(s/'mtproto/connection_tcp.cpp','''	const auto proxyProtocol = (_proxy.type == ProxyData::Type::Mtproto)
		|| (_proxy.type == ProxyData::Type::Web);
	const auto secret = proxyProtocol
		? _proxy.secretFromMtprotoPassword()
		: protocolSecret;
	if (proxyProtocol) {
		_address = _proxy.host;
		_port = _proxy.port;
		_protocol = Protocol::Create(secret);
	} else {
		_address = address;
		_port = port;
		_protocol = Protocol::Create(secret);
	}
	_socket = (_proxy.type == ProxyData::Type::Web)
		? std::make_unique<WebProxySocket>(thread(), _proxy)
		: AbstractSocket::Create(
			thread(),
			secret,
			ToNetworkProxy(_proxy),
			protocolForFiles);
	_protocolDcId = protocolDcId;''','''	const auto proxyProtocol = (_proxy.type == ProxyData::Type::Mtproto)
		|| (_proxy.type == ProxyData::Type::Web);
	const auto derenguhProxy = (_proxy.type == ProxyData::Type::Derenguh);
	const auto secret = proxyProtocol
		? _proxy.secretFromMtprotoPassword()
		: protocolSecret;
	_protocolDcId = protocolDcId;
	if (proxyProtocol || derenguhProxy) {
		_address = _proxy.host;
		_port = _proxy.port;
		_protocol = Protocol::Create(secret);
	} else {
		_address = address;
		_port = port;
		_protocol = Protocol::Create(secret);
	}
	_socket = derenguhProxy
		? std::make_unique<DerenguhSocket>(thread(), _proxy, protocolDcId)
		: (_proxy.type == ProxyData::Type::Web)
		? std::make_unique<WebProxySocket>(thread(), _proxy)
		: AbstractSocket::Create(
			thread(),
			secret,
			ToNetworkProxy(_proxy),
			protocolForFiles);''')
    patch(s/'mtproto/connection_tcp.cpp','''			(_proxy.type == ProxyData::Type::Mtproto)
				? "mtproxy "
				: (_proxy.type == ProxyData::Type::Web)
				? "webproxy "
				: "",''','''			(_proxy.type == ProxyData::Type::Mtproto)
				? "mtproxy "
				: (_proxy.type == ProxyData::Type::Web)
				? "webproxy "
				: (_proxy.type == ProxyData::Type::Derenguh)
				? "derenguh "
				: "",''')
    patch(s/'mtproto/session_private.cpp','''	if (_options->proxy.type == ProxyData::Type::Mtproto
		|| _options->proxy.type == ProxyData::Type::Web) {''','''	if (_options->proxy.type == ProxyData::Type::Mtproto
		|| _options->proxy.type == ProxyData::Type::Web
		|| _options->proxy.type == ProxyData::Type::Derenguh) {''')
    patch(s/'mtproto/session.cpp','''	const auto useHttp = (proxyType != ProxyData::Type::Mtproto)
		&& (proxyType != ProxyData::Type::Web);''','''	const auto useHttp = (proxyType != ProxyData::Type::Mtproto)
		&& (proxyType != ProxyData::Type::Web)
		&& (proxyType != ProxyData::Type::Derenguh);''')
    # proxy box UI
    p=s/'boxes/connection_box.cpp'
    patch(p,'#include "mtproto/web_proxy/web_proxy_transport.h"','#include "mtproto/web_proxy/web_proxy_transport.h"\n#include "derenguh/derenguh_protocol.h"\n#include <QtCore/QUrlQuery>')
    patch(p,'''		R"((?:https?:\\/\\/[^\\s]+|tg:\\/\\/[^\\s]+|(?:www\\.)?(?:t\\.me|telegram\\.me|telegram\\.dog)\\/[^\\s]+))",''','''		R"((?:https?:\\/\\/[^\\s]+|tg:\\/\\/[^\\s]+|derenguh:\\/\\/[^\\s]+|(?:www\\.)?(?:t\\.me|telegram\\.me|telegram\\.dog)\\/[^\\s]+))",''')
    patch(p,'''	} else if (type == ProxyData::Type::Mtproto || web) {
		proxy.password = fields.value(u"secret"_q);''','''	} else if (type == ProxyData::Type::Derenguh) {
		proxy.user = fields.value(u"sni"_q);
		proxy.password = fields.value(u"key"_q);
		proxy.password.replace('+', '-').replace('/', '_');
	} else if (type == ProxyData::Type::Mtproto || web) {
		proxy.password = fields.value(u"secret"_q);''')
    patch(p,'''[[nodiscard]] ProxyData ProxyDataFromLocalUrl(const QString &local) {
	const auto protocol = u"tg://"_q;''','''[[nodiscard]] ProxyData ProxyDataFromLocalUrl(const QString &local) {
	if (local.startsWith(u"derenguh://proxy?"_q, Qt::CaseInsensitive)) {
		const auto url = QUrl(local);
		const auto q = QUrlQuery(url);
		auto fields = QMap<QString, QString>();
		fields.insert(u"server"_q, q.queryItemValue(u"server"_q));
		fields.insert(u"port"_q, q.queryItemValue(u"port"_q));
		fields.insert(u"sni"_q, q.queryItemValue(u"sni"_q));
		fields.insert(u"key"_q, q.queryItemValue(u"key"_q));
		return ProxyDataFromFields(ProxyData::Type::Derenguh, fields);
	}
	const auto protocol = u"tg://"_q;''')
    patch(p,'''		{ Type::Web, u"WEB"_q },
	};''','''		{ Type::Web, u"WEB"_q },
		{ Type::Derenguh, u"DERENGUHGRAM PROXY"_q },
	};''')
    patch(p,'''	result.user = (result.type == Type::Mtproto || web)
		? QString()
		: _user->getLastText();
	result.password = (result.type == Type::Mtproto || web)
		? _secret->getLastText()
		: _password->getLastText();''','''	result.user = (result.type == Type::Derenguh)
		? _sni->getLastText().trimmed().toLower()
		: (result.type == Type::Mtproto || web)
		? QString()
		: _user->getLastText();
	result.password = (result.type == Type::Mtproto || web || result.type == Type::Derenguh)
		? _secret->getLastText()
		: _password->getLastText();''')
    patch(p,'''	} else if ((result.type == Type::Mtproto || web) && !result.valid()) {
		_secret->showError();''','''	} else if ((result.type == Type::Mtproto || web || result.type == Type::Derenguh) && !result.valid()) {
		if (result.type == Type::Derenguh && result.user.isEmpty()) _sni->showError(); else _secret->showError();''')
    patch(p,'''	mtproto->add(std::move(secretWrap), st::proxyEditInputPadding);
}''','''	mtproto->add(std::move(secretWrap), st::proxyEditInputPadding);
	_sniWrap = mtproto->add(object_ptr<Ui::SlideWrap<Ui::VerticalLayout>>(mtproto, object_ptr<Ui::VerticalLayout>(mtproto)));
	const auto sniContent = _sniWrap->entity();
	addLabel(sniContent, QStringLiteral("SNI (маскировка под стриминговый сервис)"));
	_sni = sniContent->add(object_ptr<Ui::InputField>(sniContent, st::connectionUserInputField, rpl::single(QString::fromLatin1(derenguh::kSniChoices[0].host)), (data.type == Type::Derenguh) ? data.user : QString()), st::proxyEditInputPadding);
}''')
    patch(p,'''		const auto mtprotoShown = (type == Type::Mtproto || web);''','''		const auto derenguh = (type == Type::Derenguh);
		const auto mtprotoShown = (type == Type::Mtproto || web || derenguh);''')
    patch(p,'''		_mtprotoCredentials->toggle(mtprotoShown, anim::type::instant);
		_aboutSponsored->toggle(mtprotoShown, anim::type::instant);''','''		_mtprotoCredentials->toggle(mtprotoShown, anim::type::instant);
		_sniWrap->toggle(derenguh, anim::type::instant);
		_aboutSponsored->toggle(mtprotoShown && !derenguh, anim::type::instant);''')
    patch(p,'''		_secret->setFocusPolicy(
			mtprotoShown ? Qt::StrongFocus : Qt::NoFocus);''','''		_secret->setFocusPolicy(
			mtprotoShown ? Qt::StrongFocus : Qt::NoFocus);
		_sni->setFocusPolicy(derenguh ? Qt::StrongFocus : Qt::NoFocus);''')
    patch(p,'''		(data.type == Type::Mtproto || data.type == Type::Web)
			? data.password
			: QString());''','''		(data.type == Type::Mtproto || data.type == Type::Web || data.type == Type::Derenguh)
			? data.password
			: QString());''')
    patch(p,'''		case Type::Web: return u"WEB"_q;
		}
		Unexpected("Proxy type in ProxiesBoxController::updateView.");''','''		case Type::Web: return u"WEB"_q;
		case Type::Derenguh: return u"DERENGUH"_q;
		}
		Unexpected("Proxy type in ProxiesBoxController::updateView.");''')
    # ProxyBox members
    patch(p,'''	QPointer<Ui::InputField> _webHost;''','''	QPointer<Ui::InputField> _webHost;
	QPointer<Ui::InputField> _sni;
	QPointer<Ui::SlideWrap<Ui::VerticalLayout>> _sniWrap;''')
    # submit focus for Derenguh
    patch(p,'''			if (_type->current() == Type::Mtproto) {
				_secret->setFocus();''','''			if (_type->current() == Type::Mtproto || _type->current() == Type::Derenguh) {
				_secret->setFocus();''')
    patch(s/'boxes/connection_box.cpp','''		case Type::None:
		case Type::Http: return QString();''','''		case Type::None:
		case Type::Http:
		case Type::Derenguh: return QString();''')
    patch(s/'core/external_control.cpp','''	case MTP::ProxyData::Type::Web: return u"web"_q;''','''	case MTP::ProxyData::Type::Web: return u"web"_q;
	case MTP::ProxyData::Type::Derenguh: return u"derenguh"_q;''')
    patch(s/'test/test_widget_fixture.cpp','''	case Type::Web: return u"web"_q;''','''	case Type::Web: return u"web"_q;
	case Type::Derenguh: return u"derenguh"_q;''')
    # Privacy gates
    patch(s/'api/api_updates.cpp','#include "api/api_updates.h"','#include "api/api_updates.h"\n#include "derenguh/privacy_settings.h"')
    patch(s/'api/api_updates.cpp','''	bool isOnline = Core::App().hasActiveWindow(&session());''','''	bool isOnline = Core::App().hasActiveWindow(&session())
		&& !derenguh::PrivacySettings::instance().invisible();''')
    patch(s/'api/api_send_progress.cpp','#include "api/api_send_progress.h"','#include "api/api_send_progress.h"\n#include "derenguh/privacy_settings.h"')
    patch(s/'api/api_send_progress.cpp','''void SendProgressManager::send(const Key &key, int progress) {
	if (skipRequest(key)) {''','''void SendProgressManager::send(const Key &key, int progress) {
	if (derenguh::PrivacySettings::instance().noTyping() || skipRequest(key)) {''')
    patch(s/'data/data_histories.cpp','#include "data/data_histories.h"','#include "data/data_histories.h"\n#include "derenguh/privacy_settings.h"')
    patch(s/'data/data_histories.cpp','''void Histories::sendReadRequests() {
	DEBUG_LOG(("Reading: send requests with count %1.").arg(_states.size()));''','''void Histories::sendReadRequests() {
	if (derenguh::PrivacySettings::instance().noReadReceipts()) return;
	DEBUG_LOG(("Reading: send requests with count %1.").arg(_states.size()));''')
    patch(s/'data/data_replies_list.cpp','#include "data/data_replies_list.h"','#include "data/data_replies_list.h"\n#include "derenguh/privacy_settings.h"')
    patch(s/'data/data_replies_list.cpp','''void RepliesList::sendReadTillRequest() {
	if (_readRequestTimer.isActive()) {''','''void RepliesList::sendReadTillRequest() {
	if (derenguh::PrivacySettings::instance().noReadReceipts()) return;
	if (_readRequestTimer.isActive()) {''')
    patch(s/'apiwrap.cpp','#include "apiwrap.h"','#include "apiwrap.h"\n#include "derenguh/privacy_settings.h"')
    patch(s/'apiwrap.cpp','''void ApiWrap::markContentsRead(
		const base::flat_set<not_null<HistoryItem*>> &items) {
	auto markedIds''','''void ApiWrap::markContentsRead(
		const base::flat_set<not_null<HistoryItem*>> &items) {
	if (derenguh::PrivacySettings::instance().noReadReceipts()) return;
	auto markedIds''')
    patch(s/'apiwrap.cpp','''void ApiWrap::markContentsRead(not_null<HistoryItem*> item) {
	if (!item->markContentsRead(true)''','''void ApiWrap::markContentsRead(not_null<HistoryItem*> item) {
	if (derenguh::PrivacySettings::instance().noReadReceipts()) return;
	if (!item->markContentsRead(true)''')
    # Main menu entry
    patch(s/'window/window_main_menu.cpp','#include "window/window_main_menu.h"','#include "window/window_main_menu.h"\n#include "derenguh/derenguh_box.h"')
    patch(s/'window/window_main_menu.cpp','''	addAction(
		tr::lng_menu_settings(),
		{ &st::menuIconSettings }
	)->setClickedCallback([=] {
		controller->showSettings();
	});''','''	addAction(
		tr::lng_menu_settings(),
		{ &st::menuIconSettings }
	)->setClickedCallback([=] {
		controller->showSettings();
	});
	addAction(
		rpl::single(QStringLiteral("DerenguhGram")),
		{ &st::menuIconLock }
	)->setClickedCallback([=] {
		derenguh::ShowDerenguhBox(controller);
	});''')
    # CMake sources
    patch(t/'Telegram/CMakeLists.txt','''    mtproto/details/mtproto_web_proxy_socket.cpp
    mtproto/details/mtproto_web_proxy_socket.h''','''    mtproto/details/mtproto_web_proxy_socket.cpp
    mtproto/details/mtproto_web_proxy_socket.h
    mtproto/details/mtproto_derenguh_socket.cpp
    mtproto/details/mtproto_derenguh_socket.h
    derenguh/derenguh_protocol.h
    derenguh/derenguh_faketls.cpp
    derenguh/derenguh_faketls.h
    derenguh/derenguh_compression.cpp
    derenguh/derenguh_compression.h
    derenguh/privacy_settings.cpp
    derenguh/privacy_settings.h
    derenguh/derenguh_box.cpp
    derenguh/derenguh_box.h''')
    print('Desktop integration applied')
if __name__=='__main__': main()
