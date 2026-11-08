// SPDX-License-Identifier: GPL-3.0-only
#include "derenguh/derenguh_box.h"
#include "derenguh/privacy_settings.h"
#include "boxes/connection_box.h"
#include "core/application.h"
#include "core/core_settings.h"
#include "core/file_utilities.h"
#include "core/sandbox.h"
#include "ui/boxes/confirm_box.h"
#include "ui/widgets/checkbox.h"
#include "ui/widgets/labels.h"
#include "ui/widgets/buttons.h"
#include "ui/wrap/vertical_layout.h"
#include "window/window_session_controller.h"
#include "styles/style_boxes.h"
#include "styles/style_settings.h"
#include "styles/style_layers.h"
#include "boxes/abstract_box.h"
#include "ui/boxes/generic_box.h"
#include "styles/style_menu_icons.h"
#include <QtCore/QDir>
#include <QtCore/QFile>
#include <QtCore/QFileInfo>
#include <QtCore/QDateTime>
#include <QtWidgets/QPlainTextEdit>
#include <QtWidgets/QFileDialog>
namespace derenguh {
namespace {
void AddLabel(not_null<Ui::VerticalLayout*> c, const QString &text) {
    c->add(object_ptr<Ui::FlatLabel>(c, text, st::boxLabel), st::boxRowPadding);
}
void ExportLogs(QWidget *parent) {
    FileDialog::GetWritePath(parent, QStringLiteral("Сохранить журнал DerenguhGram"), QStringLiteral("Text (*.txt);;All files (*)"),
        QStringLiteral("derenguh-log-%1.txt").arg(QDateTime::currentDateTime().toString(QStringLiteral("yyyyMMdd-HHmmss"))),
        [=](QString &&path) {
            QFile out(path);
            if (!out.open(QIODevice::WriteOnly)) return;
            const QString logDir = cWorkingDir() + u"DebugLogs"_q;
            QDir dir(logDir);
            const auto files = dir.entryInfoList(QDir::Files, QDir::Time);
            for (const auto &fi : files) { QFile f(fi.absoluteFilePath()); if (f.open(QIODevice::ReadOnly)) { out.write(f.readAll()); out.write("\n"); } }
            if (files.isEmpty()) out.write("DerenguhGram: DebugLogs пусты. Включите debug logging или используйте ClanSecrets во время работы прокси.\n");
        });
}
void ExportMedia(Window::SessionController *controller, QWidget *parent) {
    if (!controller) return;
    const auto src = Core::App().settings().downloadPath();
    FileDialog::GetFolder(parent, QStringLiteral("Куда сохранить обычные загруженные медиа"), src,
        [=](QString &&dst) {
            QDir().mkpath(dst);
            QDir d(src);
            int n = 0;
            const auto files = d.entryInfoList(QDir::Files);
            for (const auto &fi : files) {
                const QString target = dst + '/' + fi.fileName();
                if (!QFile::exists(target) && QFile::copy(fi.absoluteFilePath(), target)) ++n;
            }
            Ui::show(Ui::MakeInformBox(QStringLiteral("Скопировано файлов: %1\nЗащищённые/самоуничтожающиеся медиа не перехватываются.").arg(n)));
        });
}
} // namespace
void ShowDerenguhBox(Window::SessionController *controller) {
    auto box = Box([=](not_null<Ui::GenericBox*> box) {
        box->setTitle(QStringLiteral("DerenguhGram"));
        box->addButton(tr::lng_about_done(), [=] { box->closeBox(); });
        const auto content = box->verticalLayout().get();
        AddLabel(content, QStringLiteral("DerenguhGram Proxy · Приватность · ClanSecrets"));
        content->add(object_ptr<Ui::SettingsButton>(content, QStringLiteral("Настройки прокси (DerenguhGram Proxy)"), st::settingsButton), st::boxRowPadding)
            ->setClickedCallback([=] {
                if (controller) ProxiesBoxController::Show(controller);
                else Ui::show(ProxiesBoxController::CreateOwningBox(&Core::App().activeAccount()));
            });
        AddLabel(content, QStringLiteral("Приватность (подавляет только ваши исходящие сигналы)"));
        auto &p = PrivacySettings::instance();
        const auto addCheck = [&](const QString &text, bool checked, Fn<void(bool)> set) {
            auto check = content->add(object_ptr<Ui::Checkbox>(content, text, checked, st::defaultCheck), st::boxRowPadding);
            check->checkedChanges() | rpl::on_next([=](bool v) { set(v); }, check->lifetime());
        };
        addCheck(QStringLiteral("Невидимка"), p.invisible(), [&](bool v){ p.setInvisible(v); });
        addCheck(QStringLiteral("Нечиталка"), p.noReadReceipts(), [&](bool v){ p.setNoReadReceipts(v); });
        addCheck(QStringLiteral("Неписалка"), p.noTyping(), [&](bool v){ p.setNoTyping(v); });
        AddLabel(content, QStringLiteral("ClanSecrets"));
        const QString cache = cWorkingDir() + u"tdata"_q;
        AddLabel(content, QStringLiteral("Кэш/данные: %1").arg(cache));
        content->add(object_ptr<Ui::SettingsButton>(content, QStringLiteral("Открыть папку кэша"), st::settingsButton), st::boxRowPadding)
            ->setClickedCallback([=] { File::ShowInFolder(cache); });
        content->add(object_ptr<Ui::SettingsButton>(content, QStringLiteral("Просмотр журнала"), st::settingsButton), st::boxRowPadding)
            ->setClickedCallback([=] {
                Ui::show(Box([=](not_null<Ui::GenericBox*> logBox) {
                    logBox->setTitle(QStringLiteral("Журнал DerenguhGram"));
                    logBox->addButton(tr::lng_about_done(), [=] { logBox->closeBox(); });
                    auto edit = logBox->addRow(object_ptr<QPlainTextEdit>(logBox));
                    edit->setReadOnly(true); edit->setMinimumSize(480, 320);
                    QDir dir(cWorkingDir() + u"DebugLogs"_q);
                    QString text;
                    const auto files = dir.entryInfoList(QDir::Files, QDir::Time);
                    for (int i = 0; i < std::min<int>(3, int(files.size())); ++i) { QFile f(files[i].absoluteFilePath()); if (f.open(QIODevice::ReadOnly)) text += QString::fromUtf8(f.read(256 * 1024)) + '\n'; }
                    edit->setPlainText(text.isEmpty() ? QStringLiteral("Журнал пуст.") : text);
                }));
            });
        content->add(object_ptr<Ui::SettingsButton>(content, QStringLiteral("Экспорт журнала"), st::settingsButton), st::boxRowPadding)
            ->setClickedCallback([=] { ExportLogs(box); });
        content->add(object_ptr<Ui::SettingsButton>(content, QStringLiteral("Экспорт обычных медиа из загрузок"), st::settingsButton), st::boxRowPadding)
            ->setClickedCallback([=] { ExportMedia(controller, box); });
        AddLabel(content, QStringLiteral("Кэш Telegram зашифрован. Расшифровка выполняется самим клиентом при просмотре; ClanSecrets не обходит защиту одноразовых медиа."));
    });
    if (controller) controller->show(std::move(box)); else Ui::show(std::move(box));
}
} // namespace
