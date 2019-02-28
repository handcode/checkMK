// watest.cpp : This file contains the 'main' function. Program execution begins
// and ends there.
//
#include "pch.h"

#include <time.h>

#include <chrono>
#include <filesystem>
#include <future>
#include <string_view>

#include "common/cfg_info.h"

#include "read_file.h"

#include "cfg.h"
#include "cfg_details.h"

#include "cma_core.h"
#include "service_processor.h"

#include "providers/ohm.h"

namespace cma::provider {  // to become friendly for wtools classes
TEST(SectionProviderOhm, Construction) {
    OhmProvider ohm(kOhm, ',');
    EXPECT_EQ(ohm.getUniqName(), cma::section::kOhm);
}

TEST(SectionProviderOhm, ReadData) {
    namespace fs = std::filesystem;
    cma::srv::TheMiniProcess oprocess;

    fs::path ohm_exe = GetOhmCliPath();
    std::error_code ec;
    auto exists = fs::exists(ohm_exe, ec);
    auto regular_file = fs::is_regular_file(ohm_exe, ec);
    ASSERT_TRUE(exists && regular_file)
        << "not found " << ohm_exe.u8string()
        << " probably directories are not ready to test\n";

    auto ret = oprocess.start(ohm_exe.wstring());
    ASSERT_TRUE(ret);
    ::Sleep(500);
    EXPECT_TRUE(oprocess.running());

    OhmProvider ohm(provider::kOhm, ',');

    if (cma::tools::win::IsElevated()) {
        std::string out;
        for (auto i = 0; i < 10; ++i) {
            out = ohm.generateContent(section::kUseEmbeddedName);
            if (!out.empty()) break;
            ::Sleep(500);
        }
        EXPECT_TRUE(!out.empty());
        if (!out.empty()) {
            // testing output
            auto table = cma::tools::SplitString(out, "\n");

            // section header:
            EXPECT_TRUE(table.size() > 2);
            EXPECT_EQ(table[0], "<<<openhardwaremonitor:sep(44)>>>");

            // table header:
            auto header = cma::tools::SplitString(table[1], ",");
            EXPECT_EQ(header.size(), 5);
            if (header.size() >= 5) {
                const char* expected_strings[] = {"Index", "Name", "Parent",
                                                  "SensorType", "Value"};
                int index = 0;
                for (auto& str : expected_strings) {
                    EXPECT_EQ(str, header[index++]);
                }
            }

            // table body:
            for (size_t i = 2; i < table.size(); i++) {
                auto f_line = cma::tools::SplitString(table[i], ",");
                EXPECT_EQ(f_line.size(), 5);
            }
        }

    } else {
        XLOG::stdio(
            "No testing of OpenHardwareMonitor. Program must be elevated");
    }

    ret = oprocess.stop();
    EXPECT_FALSE(oprocess.running());
    EXPECT_TRUE(ret);
}

}  // namespace cma::provider

// START STOP testing
namespace cma::srv {
TEST(SectionProviderOhm, StartStop) {
    namespace fs = std::filesystem;
    cma::srv::TheMiniProcess oprocess;
    EXPECT_EQ(oprocess.process_id_, 0);
    EXPECT_EQ(oprocess.process_handle_, INVALID_HANDLE_VALUE);
    EXPECT_EQ(oprocess.thread_handle_, INVALID_HANDLE_VALUE);

    fs::path ohm_exe = cma::cfg::GetRootDir();
    ohm_exe /= cma::cfg::dirs::kAgentBin;
    ohm_exe /= cma::provider::kOpenHardwareMonitorCli;
    std::error_code ec;
    auto exists = fs::exists(ohm_exe, ec);
    EXPECT_EQ(cma::provider::GetOhmCliPath(), ohm_exe);
    auto regular_file = fs::is_regular_file(ohm_exe, ec);
    ASSERT_TRUE(exists && regular_file)
        << "not found " << ohm_exe.u8string()
        << " probably directories are not ready to test\n";

    auto ret = oprocess.start(ohm_exe.wstring());
    ASSERT_TRUE(ret);
    ::Sleep(500);
    EXPECT_TRUE(oprocess.running());

    ret = oprocess.stop();
    EXPECT_FALSE(oprocess.running());
    EXPECT_EQ(oprocess.process_id_, 0);
    EXPECT_EQ(oprocess.process_handle_, INVALID_HANDLE_VALUE);
    EXPECT_EQ(oprocess.thread_handle_, INVALID_HANDLE_VALUE);
    EXPECT_TRUE(ret);
}
}  // namespace cma::srv
