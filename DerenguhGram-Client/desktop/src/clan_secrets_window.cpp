// SPDX-License-Identifier: GPL-3.0-only
#include "clan_secrets_window.h"

#include <QTabWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QPlainTextEdit>
#include <QLineEdit>
#include <QListWidget>
#include <QLabel>
#include <QPushButton>
#include <QDesktopServices>
#include <QUrl>
#include <QDir>
#include <QFileInfo>
#include <QStandardPaths>
#include <QDateTime>
#include <QMessageBox>
#include <QClipboard>
#include <QGuiApplication>

namespace derenguh {

ClanSecretsWindow::ClanSecretsWindow(QWidget *parent) : QDialog(parent) {
    setWindowTitle(QStringLiteral("ClanSecrets"));
    resize(720, 520);

    auto *layout = new QVBoxLayout(this);
    auto *tabs = new QTabWidget(this);
    tabs->addTab(buildLogsTab(), QStringLiteral("Логи"));
    tabs->addTab(buildCacheTab(), QStringLiteral("Кэш"));
    tabs->addTab(buildSecretsTab(), QStringLiteral("ClanSecrets"));
    layout->addWidget(tabs);

    auto *closeBtn = new QPushButton(QStringLiteral("Закрыть"), this);
    connect(closeBtn, &QPushButton::clicked, this, &QDialog::accept);
    auto *bottom = new QHBoxLayout();
    bottom->addStretch();
    bottom->addWidget(closeBtn);
    layout->addLayout(bottom);

    // Default export dir: <AppData>/ClanSecrets (only content the user may keep).
    _exportDir = QStandardPaths::writableLocation(QStandardPaths::AppDataLocation)
                 + QStringLiteral("/ClanSecrets");
    QDir().mkpath(_exportDir);
}

QWidget *ClanSecretsWindow::buildLogsTab() {
    auto *w = new QWidget(this);
    auto *l = new QVBoxLayout(w);

    _version = new QLabel(QStringLiteral("Версия: —"), w);
    _proxyStatus = new QLabel(QStringLiteral("Прокси: не подключён"), w);
    l->addWidget(_version);
    l->addWidget(_proxyStatus);

    _logs = new QPlainTextEdit(w);
    _logs->setReadOnly(true);
    _logs->setMaximumBlockCount(5000); // bounded memory
    l->addWidget(_logs);

    auto *row = new QHBoxLayout();
    auto *copyBtn = new QPushButton(QStringLiteral("Копировать логи"), w);
    connect(copyBtn, &QPushButton::clicked, this, [this]() {
        QGuiApplication::clipboard()->setText(_logs->toPlainText());
    });
    auto *clearBtn = new QPushButton(QStringLiteral("Очистить"), w);
    connect(clearBtn, &QPushButton::clicked, _logs, &QPlainTextEdit::clear);
    row->addWidget(copyBtn);
    row->addWidget(clearBtn);
    row->addStretch();
    l->addLayout(row);
    return w;
}

QWidget *ClanSecretsWindow::buildCacheTab() {
    auto *w = new QWidget(this);
    auto *l = new QVBoxLayout(w);

    l->addWidget(new QLabel(QStringLiteral("Папка кэша клиента:"), w));
    auto *pathRow = new QHBoxLayout();
    _cachePath = new QLineEdit(w);
    _cachePath->setReadOnly(true);
    auto *openBtn = new QPushButton(QStringLiteral("Открыть"), w);
    connect(openBtn, &QPushButton::clicked, this, &ClanSecretsWindow::openCacheFolder);
    pathRow->addWidget(_cachePath);
    pathRow->addWidget(openBtn);
    l->addLayout(pathRow);

    l->addWidget(new QLabel(QStringLiteral("Файлы вашего кэша (только ваши данные):"), w));
    _cacheList = new QListWidget(w);
    l->addWidget(_cacheList);

    auto *refreshBtn = new QPushButton(QStringLiteral("Обновить список"), w);
    connect(refreshBtn, &QPushButton::clicked, this, &ClanSecretsWindow::refreshCacheList);
    l->addWidget(refreshBtn);

    auto *note = new QLabel(QStringLiteral(
        "Медиафайлы кэша показаны как есть. Сообщения в tdata зашифрованы локальным\n"
        "ключом сессии; расшифровка выполняется только для ВАШЕГО аккаунта через\n"
        "Storage-слой клиента (см. docs/CLANSECRETS.md)."), w);
    note->setWordWrap(true);
    l->addWidget(note);
    return w;
}

QWidget *ClanSecretsWindow::buildSecretsTab() {
    auto *w = new QWidget(this);
    auto *l = new QVBoxLayout(w);

    auto *title = new QLabel(QStringLiteral("<b>Папка ClanSecrets</b>"), w);
    l->addWidget(title);

    auto *explain = new QLabel(QStringLiteral(
        "Здесь сохраняется только тот контент, который вам разрешено хранить:\n"
        "• обычные (незащищённые) фото/видео/файлы из чатов;\n"
        "• медиа, которые отправитель прислал без таймера и без запрета сохранения.\n\n"
        "Самоуничтожающиеся и «одноразовые» сообщения НЕ перехватываются: отправитель\n"
        "явно включил защиту, и обход этого нарушил бы его согласие. Вместо скрытого\n"
        "сохранения используйте кнопку ниже — она отправит запрос на постоянную копию."), w);
    explain->setWordWrap(true);
    l->addWidget(explain);

    auto *openExport = new QPushButton(QStringLiteral("Открыть папку ClanSecrets"), w);
    connect(openExport, &QPushButton::clicked, this, &ClanSecretsWindow::openExportFolder);
    l->addWidget(openExport);

    auto *requestBtn = new QPushButton(QStringLiteral("Запросить постоянную копию у отправителя…"), w);
    connect(requestBtn, &QPushButton::clicked, this, &ClanSecretsWindow::requestPermanentCopy);
    l->addWidget(requestBtn);

    l->addStretch();
    return w;
}

void ClanSecretsWindow::appendLog(const QString &line) {
    if (!_logs) return;
    _logs->appendPlainText(QDateTime::currentDateTime().toString(QStringLiteral("HH:mm:ss "))
                           + line);
}

void ClanSecretsWindow::setProxyStatus(const QString &status) {
    if (_proxyStatus) _proxyStatus->setText(QStringLiteral("Прокси: ") + status);
}

void ClanSecretsWindow::setVersionInfo(const QString &version) {
    if (_version) _version->setText(QStringLiteral("Версия: ") + version);
}

void ClanSecretsWindow::setCachePath(const QString &path) {
    if (_cachePath) _cachePath->setText(path);
    refreshCacheList();
}

void ClanSecretsWindow::openCacheFolder() {
    if (_cachePath && !_cachePath->text().isEmpty())
        QDesktopServices::openUrl(QUrl::fromLocalFile(_cachePath->text()));
}

void ClanSecretsWindow::refreshCacheList() {
    if (!_cacheList || !_cachePath) return;
    _cacheList->clear();
    QDir dir(_cachePath->text());
    if (!dir.exists()) return;
    const auto entries = dir.entryInfoList(QDir::Files | QDir::Dirs | QDir::NoDotAndDotDot,
                                           QDir::Name);
    for (const auto &fi : entries) {
        const QString kind = fi.isDir() ? QStringLiteral("[dir] ") : QString();
        _cacheList->addItem(QStringLiteral("%1%2  (%3 bytes)")
            .arg(kind, fi.fileName()).arg(fi.size()));
    }
}

void ClanSecretsWindow::openExportFolder() {
    QDir().mkpath(_exportDir);
    QDesktopServices::openUrl(QUrl::fromLocalFile(_exportDir));
}

void ClanSecretsWindow::requestPermanentCopy() {
    // Consent-respecting alternative to covert ephemeral capture: the integration
    // layer opens a message composer addressed to the sender with a polite request.
    // Here we only explain the flow; the actual send is wired in the fork (see docs).
    QMessageBox::information(this, QStringLiteral("Запрос копии"),
        QStringLiteral("Будет открыт чат с отправителем и черновик сообщения:\n\n"
                       "«Привет! Можешь прислать это фото/видео ещё раз без таймера? "
                       "Хочу сохранить.»\n\n"
                       "Так решение остаётся за отправителем."));
}

} // namespace derenguh
